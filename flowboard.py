#!/usr/bin/env python3
"""FlowBoard: a dependency-free, local project and todo board."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "flowboard_data.json"
MAX_BODY_BYTES = 2 * 1024 * 1024
DATA_LOCK = threading.Lock()


HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f3efe5">
  <title>FlowBoard · Project Flow Board</title>
  <style>
    :root {
      --ink: #25231f;
      --muted: #777168;
      --paper: #f4f0e7;
      --paper-deep: #e8e1d4;
      --line: rgba(50, 45, 37, .14);
      --accent: #ee6c4d;
      --white: #fffdf8;
      --shadow: 0 18px 42px rgba(56, 49, 38, .12), 0 2px 8px rgba(56, 49, 38, .08);
      --radius: 18px;
    }

    * { box-sizing: border-box; }

    html { min-height: 100%; background: var(--paper); }

    body {
      min-height: 100vh;
      margin: 0;
      color: var(--ink);
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(circle at 8% 4%, rgba(238, 108, 77, .10), transparent 24rem),
        radial-gradient(circle at 90% 12%, rgba(69, 123, 157, .09), transparent 27rem),
        linear-gradient(rgba(71, 64, 54, .035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(71, 64, 54, .035) 1px, transparent 1px),
        var(--paper);
      background-size: auto, auto, 28px 28px, 28px 28px, auto;
    }

    button, input, select { font: inherit; }
    button, select { cursor: pointer; }

    button:focus-visible, input:focus-visible, select:focus-visible {
      outline: 3px solid rgba(69, 123, 157, .35);
      outline-offset: 2px;
    }

    .app-shell { width: min(1600px, 100%); margin: 0 auto; padding: 28px 32px 48px; }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--line);
    }

    .brand { display: flex; align-items: center; gap: 13px; }

    .brand-mark {
      display: grid;
      place-items: center;
      width: 42px;
      height: 42px;
      border-radius: 13px 13px 13px 5px;
      background: var(--ink);
      color: var(--white);
      font-weight: 900;
      font-size: 20px;
      transform: rotate(-2deg);
      box-shadow: 5px 5px 0 rgba(238, 108, 77, .7);
    }

    .brand-copy h1 { margin: 0; font-family: Georgia, "Songti SC", serif; font-size: 25px; letter-spacing: -.02em; }
    .brand-copy p { margin: 3px 0 0; color: var(--muted); font-size: 13px; }

    .save-status {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }

    .save-dot { width: 8px; height: 8px; border-radius: 50%; background: #5f9c78; box-shadow: 0 0 0 4px rgba(95, 156, 120, .12); }
    .save-status.saving .save-dot { background: #dc9f3c; animation: pulse 1s infinite; }
    .save-status.error .save-dot { background: #c94f4f; }

    .topbar-actions { display: flex; align-items: center; gap: 15px; }

    .language-button {
      min-width: 48px;
      height: 34px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: rgba(255, 253, 248, .58);
      color: var(--ink);
      font-size: 12px;
      font-weight: 800;
    }

    .language-button:hover { background: var(--white); }

    @keyframes pulse { 50% { opacity: .4; } }

    .hero {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 28px;
      padding: 24px 0;
    }

    .hero-meta { margin: 0; color: var(--muted); font-size: 14px; }

    .hero-actions { display: flex; align-items: center; gap: 12px; }

    .primary-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-height: 44px;
      padding: 0 18px;
      border: 0;
      border-radius: 13px;
      background: var(--ink);
      color: white;
      font-weight: 700;
      box-shadow: 0 7px 0 #c95b42;
      transition: transform .15s, box-shadow .15s;
    }

    .primary-button:hover { transform: translateY(-2px); box-shadow: 0 9px 0 #c95b42; }
    .primary-button:active { transform: translateY(5px); box-shadow: 0 2px 0 #c95b42; }
    .primary-button .plus { font-size: 22px; line-height: 1; }

    .clear-all-button {
      min-height: 44px;
      padding: 0 16px;
      border: 1px solid rgba(158, 49, 49, .28);
      border-radius: 13px;
      background: rgba(255, 253, 248, .58);
      color: #9e3131;
      font-weight: 750;
    }

    .clear-all-button:hover:not(:disabled) { background: rgba(174, 54, 54, .10); }
    .clear-all-button:disabled, .icon-button:disabled { cursor: not-allowed; opacity: .38; }

    .board {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(315px, 1fr));
      align-items: start;
      gap: 24px;
    }

    .project-card {
      --note: #f6df86;
      --note-soft: #fff7cf;
      position: relative;
      min-width: 0;
      overflow: hidden;
      border: 1px solid rgba(58, 51, 41, .13);
      border-radius: var(--radius) var(--radius) 8px var(--radius);
      background: linear-gradient(140deg, var(--note-soft), var(--note));
      box-shadow: var(--shadow);
      transition: transform .18s, box-shadow .18s, opacity .18s;
    }

    .project-card::after {
      content: "";
      position: absolute;
      right: 0;
      bottom: 0;
      width: 32px;
      height: 32px;
      background: linear-gradient(135deg, rgba(255,255,255,.05) 50%, rgba(69,60,46,.12) 51%);
      pointer-events: none;
    }

    .project-card:hover { transform: translateY(-3px) rotate(.15deg); box-shadow: 0 22px 50px rgba(56, 49, 38, .16); }
    .project-card.dragging { opacity: .42; transform: scale(.98); }
    .project-card.drag-over { box-shadow: 0 0 0 4px rgba(37, 35, 31, .22), var(--shadow); }

    .note-yellow { --note: #f4d86e; --note-soft: #fff5bd; }
    .note-blue { --note: #9ed4e7; --note-soft: #dff4fb; }
    .note-green { --note: #a8d9ad; --note-soft: #e2f4df; }
    .note-rose { --note: #efa9ac; --note-soft: #ffe0df; }
    .note-lilac { --note: #c9b5e9; --note-soft: #eee3fb; }

    .card-head { padding: 17px 19px 15px; border-bottom: 1px solid rgba(58, 51, 41, .12); }
    .card-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 29px; }

    .drag-handle {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 4px 6px 4px 2px;
      border: 0;
      background: transparent;
      color: rgba(37,35,31,.58);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: .04em;
      cursor: grab;
      user-select: none;
    }

    .drag-handle:active { cursor: grabbing; }
    .grip { font-size: 17px; letter-spacing: -4px; transform: rotate(90deg); }
    .head-actions { display: flex; align-items: center; gap: 5px; }

    .icon-button {
      display: grid;
      place-items: center;
      width: 29px;
      height: 29px;
      padding: 0;
      border: 0;
      border-radius: 9px;
      background: rgba(255,255,255,.34);
      color: rgba(37,35,31,.68);
    }

    .icon-button:hover { background: rgba(255,255,255,.65); color: var(--ink); }
    .icon-button.danger:hover { background: rgba(174,54,54,.13); color: #9e3131; }

    .project-title {
      width: 100%;
      margin-top: 13px;
      padding: 1px 0 4px;
      border: 0;
      border-bottom: 1px solid transparent;
      outline: 0;
      background: transparent;
      color: var(--ink);
      font-family: Georgia, "Songti SC", serif;
      font-size: 25px;
      font-weight: 700;
    }

    .project-title:hover, .project-title:focus { border-bottom-color: rgba(37,35,31,.25); }

    .project-meta { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 11px; }
    .progress { color: rgba(37,35,31,.62); font-size: 12px; font-weight: 600; }

    .priority-select, .todo-priority {
      appearance: none;
      border: 1px solid rgba(45,40,33,.14);
      border-radius: 999px;
      background: rgba(255,255,255,.43);
      color: var(--ink);
      font-size: 12px;
      font-weight: 700;
      text-align: center;
    }

    .priority-select { min-height: 29px; padding: 0 26px 0 10px; background-image: linear-gradient(45deg, transparent 50%, #5d574f 50%), linear-gradient(135deg, #5d574f 50%, transparent 50%); background-position: calc(100% - 12px) 12px, calc(100% - 8px) 12px; background-size: 4px 4px; background-repeat: no-repeat; }

    .card-body { padding: 10px 13px 18px; }
    .todo-list { display: grid; gap: 4px; min-height: 8px; }

    .todo-item {
      display: grid;
      grid-template-columns: 16px 24px minmax(0, 1fr) auto 48px 26px;
      align-items: center;
      gap: 6px;
      min-height: 42px;
      padding: 5px 5px;
      border-radius: 11px;
    }

    .todo-item:hover { background: rgba(255,255,255,.28); }
    .todo-item.todo-dragging { opacity: .38; }
    .todo-item.todo-drag-over { background: rgba(255,255,255,.54); box-shadow: inset 0 2px 0 rgba(37,35,31,.38); }

    .todo-drag-handle {
      border: 0;
      padding: 3px 0;
      background: transparent;
      color: rgba(37,35,31,.42);
      font-size: 15px;
      line-height: 1;
      cursor: grab;
      user-select: none;
    }

    .todo-drag-handle:active { cursor: grabbing; }

    .todo-check {
      appearance: none;
      display: grid;
      place-content: center;
      width: 18px;
      height: 18px;
      margin: 0;
      border: 1.5px solid rgba(37,35,31,.58);
      border-radius: 5px;
      background: rgba(255,255,255,.30);
      cursor: pointer;
    }

    .todo-check::before { content: "✓"; color: white; font-size: 13px; font-weight: 900; transform: scale(0); transition: transform .12s; }
    .todo-check:checked { border-color: #5c7563; background: #5c7563; }
    .todo-check:checked::before { transform: scale(1); }

    .todo-text {
      min-width: 0;
      padding: 3px 2px;
      border: 0;
      border-bottom: 1px solid transparent;
      background: transparent;
      color: #486f9a;
      font-size: 14px;
      line-height: 1.35;
    }

    .todo-text:hover, .todo-text:focus { border-bottom-color: rgba(37,35,31,.18); outline: 0; }
    .todo-item[data-priority="urgent"] .todo-text { color: #b63f3f; font-weight: 700; }
    .todo-item[data-priority="high"] .todo-text { color: #a85e24; font-weight: 650; }
    .todo-item[data-priority="medium"] .todo-text { color: #3d6f91; }
    .todo-item[data-priority="low"] .todo-text { color: #696f6c; }
    .todo-item.completed .todo-text { color: rgba(70,68,64,.50) !important; text-decoration: line-through; text-decoration-thickness: 1.5px; }

    .todo-priority { width: 52px; min-height: 25px; padding: 0 3px; font-size: 11px; }
    .todo-order-actions { display: flex; gap: 2px; }
    .todo-order-button { width: 23px; height: 25px; border-radius: 7px; font-size: 12px; }
    .todo-delete { opacity: 0; }
    .todo-item:hover .todo-delete, .todo-delete:focus-visible { opacity: 1; }

    .add-todo-form {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 70px 34px;
      gap: 7px;
      margin-top: 10px;
      padding: 10px 6px 1px;
      border-top: 1px dashed rgba(37,35,31,.18);
    }

    .add-todo-input {
      min-width: 0;
      height: 35px;
      padding: 0 10px;
      border: 1px solid rgba(45,40,33,.14);
      border-radius: 10px;
      background: rgba(255,255,255,.38);
      color: var(--ink);
    }

    .add-todo-input::placeholder { color: rgba(37,35,31,.48); }
    .add-todo-button { width: 34px; height: 34px; border: 0; border-radius: 10px; background: rgba(37,35,31,.88); color: white; font-size: 20px; }
    .add-todo-button:hover { background: var(--ink); }

    .empty-state {
      grid-column: 1 / -1;
      display: grid;
      place-items: center;
      min-height: 340px;
      padding: 40px;
      border: 2px dashed rgba(63,56,46,.17);
      border-radius: 24px;
      text-align: center;
    }

    .empty-note { display: grid; align-content: center; width: 180px; min-height: 135px; padding: 24px 20px; background: #f5d96f; box-shadow: 10px 12px 0 rgba(80,65,40,.10); transform: rotate(-3deg); }
    .empty-note strong { display: block; font-family: Georgia, "Songti SC", serif; font-size: 20px; line-height: 1.15; }
    .empty-note span { display: block; margin-top: 13px; color: rgba(37,35,31,.62); font-size: 13px; line-height: 1.4; }

    .modal-backdrop {
      position: fixed;
      inset: 0;
      z-index: 20;
      display: grid;
      place-items: center;
      padding: 20px;
      background: rgba(37,35,31,.38);
      backdrop-filter: blur(5px);
    }

    .modal-backdrop[hidden] { display: none; }

    .modal {
      width: min(440px, 100%);
      padding: 26px;
      border: 1px solid rgba(255,255,255,.55);
      border-radius: 22px;
      background: var(--white);
      box-shadow: 0 28px 80px rgba(30,27,22,.30);
    }

    .modal h3 { margin: 0; font-family: Georgia, "Songti SC", serif; font-size: 27px; }
    .modal p { margin: 7px 0 21px; color: var(--muted); font-size: 14px; }
    .field { display: grid; gap: 7px; margin-top: 15px; }
    .field label { color: #59544d; font-size: 12px; font-weight: 800; letter-spacing: .06em; }
    .field input, .field select { width: 100%; height: 43px; padding: 0 12px; border: 1px solid #d8d2c8; border-radius: 11px; background: white; color: var(--ink); }

    .color-picker { display: flex; gap: 10px; }
    .color-choice { position: relative; }
    .color-choice input { position: absolute; opacity: 0; pointer-events: none; }
    .color-swatch { display: block; width: 37px; height: 37px; border: 2px solid white; border-radius: 11px; box-shadow: 0 0 0 1px rgba(37,35,31,.17); cursor: pointer; }
    .color-choice input:checked + .color-swatch { box-shadow: 0 0 0 3px var(--ink); transform: rotate(-5deg); }
    .swatch-yellow { background: #f4d86e; } .swatch-blue { background: #9ed4e7; } .swatch-green { background: #a8d9ad; } .swatch-rose { background: #efa9ac; } .swatch-lilac { background: #c9b5e9; }

    .modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }
    .secondary-button { min-height: 42px; padding: 0 16px; border: 1px solid #d8d2c8; border-radius: 11px; background: white; color: var(--ink); font-weight: 700; }
    .modal .primary-button { min-height: 42px; box-shadow: none; }

    .toast {
      position: fixed;
      right: 24px;
      bottom: 24px;
      z-index: 30;
      padding: 12px 16px;
      border-radius: 12px;
      background: var(--ink);
      color: white;
      font-size: 13px;
      box-shadow: var(--shadow);
      transform: translateY(80px);
      opacity: 0;
      transition: .2s;
      pointer-events: none;
    }

    .toast.show { transform: translateY(0); opacity: 1; }

    @media (max-width: 720px) {
      .app-shell { padding: 19px 16px 36px; }
      .topbar { align-items: flex-start; }
      .topbar-actions { align-items: flex-end; flex-direction: column-reverse; gap: 9px; }
      .save-status { font-size: 11px; }
      .brand-copy p { display: none; }
      .hero { align-items: stretch; flex-direction: column; padding: 20px 0; }
      .hero-actions { align-items: stretch; flex-direction: column-reverse; }
      .hero .primary-button { width: 100%; }
      .hero .clear-all-button { width: 100%; }
      .board { grid-template-columns: 1fr; gap: 18px; }
      .project-card:hover { transform: none; }
      .todo-delete { opacity: .65; }
    }

    @media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; animation: none !important; transition: none !important; } }
  </style>
</head>
<body>
  <main class="app-shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true">F</div>
        <div class="brand-copy">
          <h1>FlowBoard</h1>
          <p id="brandTagline">A tiny local-first board for projects in motion</p>
        </div>
      </div>
      <div class="topbar-actions">
        <div class="save-status" id="saveStatus" role="status" aria-live="polite">
          <span class="save-dot"></span><span id="saveText">Loading…</span>
        </div>
        <button class="language-button" id="languageButton" type="button" title="切换到中文" aria-label="切换到中文">中文</button>
      </div>
    </header>

    <section class="hero">
      <div>
        <p class="hero-meta" id="boardStats">Loading projects…</p>
      </div>
      <div class="hero-actions">
        <button class="clear-all-button" id="clearAllButton" type="button" disabled><span id="clearAllText">Clear all</span></button>
        <button class="primary-button" id="addProjectButton" type="button"><span class="plus">＋</span><span id="addProjectText">Add a project</span></button>
      </div>
    </section>

    <section class="board" id="board" aria-label="Project note board"></section>
  </main>

  <div class="modal-backdrop" id="projectModal" hidden>
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
      <form id="projectForm">
        <h3 id="modalTitle">Add a project</h3>
        <p id="modalDescription">Give it a recognizable name. You can edit it at any time.</p>
        <div class="field">
          <label for="projectName" id="projectNameLabel">Project name</label>
          <input id="projectName" name="name" maxlength="80" autocomplete="off" placeholder="e.g. Model A training and evaluation" required>
        </div>
        <div class="field">
          <label for="projectPriority" id="projectPriorityLabel">Project priority</label>
          <select id="projectPriority" name="priority">
            <option value="high">Important</option>
            <option value="medium" selected>Normal</option>
            <option value="low">Later</option>
          </select>
        </div>
        <div class="field">
          <label id="noteColorLabel">Note color</label>
          <div class="color-picker" id="colorPicker" aria-label="Choose a note color">
            <label class="color-choice"><input type="radio" name="color" value="yellow" checked><span class="color-swatch swatch-yellow" title="Warm yellow"></span></label>
            <label class="color-choice"><input type="radio" name="color" value="blue"><span class="color-swatch swatch-blue" title="Sky blue"></span></label>
            <label class="color-choice"><input type="radio" name="color" value="green"><span class="color-swatch swatch-green" title="Grass green"></span></label>
            <label class="color-choice"><input type="radio" name="color" value="rose"><span class="color-swatch swatch-rose" title="Coral rose"></span></label>
            <label class="color-choice"><input type="radio" name="color" value="lilac"><span class="color-swatch swatch-lilac" title="Lilac"></span></label>
          </div>
        </div>
        <div class="modal-actions">
          <button class="secondary-button" id="cancelModal" type="button">Cancel</button>
          <button class="primary-button" id="createProjectButton" type="submit">Create project</button>
        </div>
      </form>
    </div>
  </div>
  <div class="toast" id="toast" role="status" aria-live="polite"></div>

  <script>
    const COLORS = ['yellow', 'blue', 'green', 'rose', 'lilac'];
    const PROJECT_PRIORITIES = ['high', 'medium', 'low'];
    const TODO_PRIORITIES = ['urgent', 'high', 'medium', 'low'];

    const I18N = {
      en: {
        pageTitle: 'FlowBoard · Project Flow Board',
        tagline: 'A tiny local-first board for projects in motion',
        loading: 'Loading…',
        loadingProjects: 'Loading projects…',
        addProject: 'Add a project',
        clearAll: 'Clear all',
        boardLabel: 'Project note board',
        modalTitle: 'Add a project',
        modalDescription: 'Give it a recognizable name. You can edit it at any time.',
        projectName: 'Project name',
        projectNamePlaceholder: 'e.g. Model A training and evaluation',
        projectPriority: 'Project priority',
        noteColor: 'Note color',
        chooseColor: 'Choose a note color',
        cancel: 'Cancel',
        createProject: 'Create project',
        colorYellow: 'Warm yellow',
        colorBlue: 'Sky blue',
        colorGreen: 'Grass green',
        colorRose: 'Coral rose',
        colorLilac: 'Lilac',
        projectPriorityHigh: 'Important',
        projectPriorityMedium: 'Normal',
        projectPriorityLow: 'Later',
        todoPriorityUrgent: 'Urgent',
        todoPriorityHigh: 'High',
        todoPriorityMedium: 'Medium',
        todoPriorityLow: 'Low',
        stats: (projects, open, completed) => `${projects} ${projects === 1 ? 'project' : 'projects'} · ${open} ${open === 1 ? 'open task' : 'open tasks'}${completed ? ` · ${completed} completed` : ''}`,
        firstProjectHint: 'Add your first project so every wait has a clear next step.',
        emptyTitle: 'No projects yet',
        emptyText: 'Add your first project above',
        dragSort: 'Drag to reorder',
        moveEarlier: 'Move earlier',
        changeColor: 'Change note color',
        clearProject: 'Clear project',
        clearTodos: 'Clear all tasks',
        dragTodo: 'Drag to reorder task',
        moveTodoUp: 'Move task up',
        moveTodoDown: 'Move task down',
        toggleTodo: 'Mark task as completed',
        todoContent: 'Task content',
        todoPriority: 'Task priority',
        deleteTodo: 'Delete task',
        progress: (completed, total) => `${completed} / ${total} completed`,
        noTodos: 'No tasks yet',
        addNextPlaceholder: 'Add the next step…',
        newTodoContent: 'New task content',
        newTodoPriority: 'New task priority',
        addTodo: 'Add task',
        untitledProject: 'Untitled project',
        untitledTodo: 'Untitled task',
        waitingSave: 'Waiting to save…',
        saving: 'Saving…',
        saved: date => `Saved · ${formatTime(date)}`,
        saveFailed: 'Save failed. Keep the script running.',
        cacheLoaded: 'Local data loaded',
        loadFailed: 'Could not load data. Refresh the page.',
        projectAdded: 'Project added to the board',
        confirmClearAll: 'Clear every project and task from this board? This cannot be undone.',
        allCleared: 'All projects cleared',
        confirmClearProject: name => `Clear “${name}” and all of its tasks? This removes the project.`,
        projectCleared: 'Project cleared',
        confirmClearTodos: name => `Clear all tasks in “${name}”? The project will remain.`,
        todosCleared: 'Project tasks cleared',
        orderUpdated: 'Project order updated',
        todoOrderUpdated: 'Task order updated',
        switchLanguage: '切换到中文',
        languageButton: '中文'
      },
      zh: {
        pageTitle: 'FlowBoard · 项目流转板',
        tagline: '让每个流转中的项目，都留在视线里',
        loading: '正在读取…',
        loadingProjects: '载入项目中…',
        addProject: '贴一个新项目',
        clearAll: '清空全部',
        boardLabel: '项目便签板',
        modalTitle: '贴一个新项目',
        modalDescription: '先给它一个容易辨认的名字，之后随时都能修改。',
        projectName: '项目名称',
        projectNamePlaceholder: '例如：模型 A 训练与测评',
        projectPriority: '项目重要程度',
        noteColor: '便签颜色',
        chooseColor: '选择便签颜色',
        cancel: '取消',
        createProject: '创建项目',
        colorYellow: '暖黄',
        colorBlue: '天蓝',
        colorGreen: '草绿',
        colorRose: '珊瑚粉',
        colorLilac: '丁香紫',
        projectPriorityHigh: '重要',
        projectPriorityMedium: '普通',
        projectPriorityLow: '稍后',
        todoPriorityUrgent: '紧急',
        todoPriorityHigh: '高',
        todoPriorityMedium: '中',
        todoPriorityLow: '低',
        stats: (projects, open, completed) => `${projects} 个项目 · ${open} 条待办未完成${completed ? ` · ${completed} 条已完成` : ''}`,
        firstProjectHint: '先贴下第一个项目，让每个等待都有下一个动作。',
        emptyTitle: '还没有项目',
        emptyText: '点击上方按钮添加第一个项目',
        dragSort: '拖动排序',
        moveEarlier: '向前移动',
        changeColor: '更换便签颜色',
        clearProject: '清空项目',
        clearTodos: '清空全部待办',
        dragTodo: '拖动调整待办顺序',
        moveTodoUp: '上移待办',
        moveTodoDown: '下移待办',
        toggleTodo: '标记待办完成',
        todoContent: '待办内容',
        todoPriority: '待办优先级',
        deleteTodo: '删除待办',
        progress: (completed, total) => `${completed} / ${total} 已完成`,
        noTodos: '还没有待办',
        addNextPlaceholder: '添加下一步…',
        newTodoContent: '新待办内容',
        newTodoPriority: '新待办优先级',
        addTodo: '添加待办',
        untitledProject: '未命名项目',
        untitledTodo: '未命名待办',
        waitingSave: '等待保存…',
        saving: '正在保存…',
        saved: date => `已保存 · ${formatTime(date)}`,
        saveFailed: '保存失败，请保持脚本运行',
        cacheLoaded: '已读取本地缓存',
        loadFailed: '读取失败，请刷新页面',
        projectAdded: '项目已贴到流转板',
        confirmClearAll: '确定清空页面中的所有项目和待办吗？此操作无法撤销。',
        allCleared: '已清空全部项目',
        confirmClearProject: name => `确定清空项目“${name}”及其中所有待办吗？项目本身也会被删除。`,
        projectCleared: '已清空项目',
        confirmClearTodos: name => `确定清空项目“${name}”中的全部待办吗？项目本身会保留。`,
        todosCleared: '已清空项目待办',
        orderUpdated: '项目顺序已更新',
        todoOrderUpdated: '待办顺序已更新',
        switchLanguage: 'Switch to English',
        languageButton: 'EN'
      }
    };

    function preferredLanguage() {
      try {
        const saved = localStorage.getItem('flowboard_language');
        if (saved === 'zh' || saved === 'en') return saved;
      } catch (_) {}
      return navigator.language.toLowerCase().startsWith('zh') ? 'zh' : 'en';
    }

    let currentLanguage = preferredLanguage();

    function t(key, ...args) {
      const value = I18N[currentLanguage][key];
      return typeof value === 'function' ? value(...args) : value;
    }

    function formatTime(date) {
      return date.toLocaleTimeString(currentLanguage === 'zh' ? 'zh-CN' : 'en-US', { hour: '2-digit', minute: '2-digit' });
    }

    let state = { version: 1, projects: [] };
    let saveTimer = null;
    let saveQueue = Promise.resolve();
    let draggedProjectId = null;
    let draggedTodo = null;
    let saveStateInfo = { kind: '', key: 'loading', args: [] };

    const board = document.getElementById('board');
    const stats = document.getElementById('boardStats');
    const modal = document.getElementById('projectModal');
    const projectForm = document.getElementById('projectForm');
    const projectName = document.getElementById('projectName');
    const saveStatus = document.getElementById('saveStatus');
    const saveText = document.getElementById('saveText');
    const toast = document.getElementById('toast');
    const languageButton = document.getElementById('languageButton');
    const clearAllButton = document.getElementById('clearAllButton');

    function id(prefix) {
      return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>'"]/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
      })[char]);
    }

    function setSaveStatus(kind, key, ...args) {
      saveStateInfo = { kind, key, args };
      saveStatus.className = `save-status ${kind || ''}`;
      saveText.textContent = t(key, ...args);
    }

    function showToast(message) {
      toast.textContent = message;
      toast.classList.add('show');
      clearTimeout(showToast.timer);
      showToast.timer = setTimeout(() => toast.classList.remove('show'), 1800);
    }

    function priorityOptions(current, values, type) {
      return values.map(value => {
        const suffix = value.charAt(0).toUpperCase() + value.slice(1);
        return `<option value="${value}" ${value === current ? 'selected' : ''}>${t(`${type}Priority${suffix}`)}</option>`;
      }).join('');
    }

    function applyLanguage() {
      document.documentElement.lang = currentLanguage === 'zh' ? 'zh-CN' : 'en';
      document.title = t('pageTitle');
      document.getElementById('brandTagline').textContent = t('tagline');
      document.getElementById('addProjectText').textContent = t('addProject');
      document.getElementById('clearAllText').textContent = t('clearAll');
      clearAllButton.title = t('clearAll');
      clearAllButton.setAttribute('aria-label', t('clearAll'));
      board.setAttribute('aria-label', t('boardLabel'));
      document.getElementById('modalTitle').textContent = t('modalTitle');
      document.getElementById('modalDescription').textContent = t('modalDescription');
      document.getElementById('projectNameLabel').textContent = t('projectName');
      projectName.placeholder = t('projectNamePlaceholder');
      document.getElementById('projectPriorityLabel').textContent = t('projectPriority');
      document.getElementById('noteColorLabel').textContent = t('noteColor');
      document.getElementById('colorPicker').setAttribute('aria-label', t('chooseColor'));
      document.getElementById('cancelModal').textContent = t('cancel');
      document.getElementById('createProjectButton').textContent = t('createProject');

      const projectPriority = document.getElementById('projectPriority');
      const selectedPriority = projectPriority.value || 'medium';
      projectPriority.innerHTML = priorityOptions(selectedPriority, PROJECT_PRIORITIES, 'project');

      const colorKeys = { yellow: 'colorYellow', blue: 'colorBlue', green: 'colorGreen', rose: 'colorRose', lilac: 'colorLilac' };
      COLORS.forEach(color => {
        const input = document.querySelector(`input[name="color"][value="${color}"]`);
        const swatch = input?.nextElementSibling;
        const label = t(colorKeys[color]);
        input?.setAttribute('aria-label', label);
        swatch?.setAttribute('title', label);
      });

      languageButton.textContent = t('languageButton');
      languageButton.title = t('switchLanguage');
      languageButton.setAttribute('aria-label', t('switchLanguage'));
      saveStatus.className = `save-status ${saveStateInfo.kind || ''}`;
      saveText.textContent = t(saveStateInfo.key, ...saveStateInfo.args);
      render();
    }

    function normalizeState(raw) {
      const projects = Array.isArray(raw?.projects) ? raw.projects : [];
      return {
        version: 1,
        projects: projects.map(project => ({
          id: String(project.id || id('project')),
          name: String(project.name || t('untitledProject')).slice(0, 80),
          color: COLORS.includes(project.color) ? project.color : 'yellow',
          priority: PROJECT_PRIORITIES.includes(project.priority) ? project.priority : 'medium',
          todos: (Array.isArray(project.todos) ? project.todos : []).map(todo => ({
            id: String(todo.id || id('todo')),
            text: String(todo.text || t('untitledTodo')).slice(0, 160),
            priority: TODO_PRIORITIES.includes(todo.priority) ? todo.priority : 'medium',
            completed: Boolean(todo.completed)
          }))
        }))
      };
    }

    function render() {
      const totalTodos = state.projects.reduce((sum, project) => sum + project.todos.length, 0);
      const completedTodos = state.projects.reduce((sum, project) => sum + project.todos.filter(todo => todo.completed).length, 0);
      const openTodos = totalTodos - completedTodos;
      clearAllButton.disabled = state.projects.length === 0;
      stats.textContent = state.projects.length
        ? t('stats', state.projects.length, openTodos, completedTodos)
        : t('firstProjectHint');

      if (!state.projects.length) {
        board.innerHTML = `<div class="empty-state">
          <div class="empty-note"><strong>${t('emptyTitle')}</strong><span>${t('emptyText')}</span></div>
        </div>`;
        return;
      }

      board.innerHTML = state.projects.map((project, index) => {
        const completed = project.todos.filter(todo => todo.completed).length;
        const todos = project.todos.map((todo, todoIndex) => `
          <div class="todo-item ${todo.completed ? 'completed' : ''}" data-project-id="${escapeHtml(project.id)}" data-todo-id="${escapeHtml(todo.id)}" data-priority="${todo.priority}">
            <button class="todo-drag-handle" draggable="true" type="button" title="${t('dragTodo')}" aria-label="${t('dragTodo')}">⠿</button>
            <input class="todo-check" data-action="toggle-todo" type="checkbox" ${todo.completed ? 'checked' : ''} aria-label="${t('toggleTodo')}">
            <input class="todo-text" data-action="edit-todo" maxlength="160" value="${escapeHtml(todo.text)}" aria-label="${t('todoContent')}">
            <select class="todo-priority" data-action="todo-priority" aria-label="${t('todoPriority')}">${priorityOptions(todo.priority, TODO_PRIORITIES, 'todo')}</select>
            <span class="todo-order-actions">
              <button class="icon-button todo-order-button" data-action="move-todo-up" type="button" title="${t('moveTodoUp')}" aria-label="${t('moveTodoUp')}" ${todoIndex === 0 ? 'disabled' : ''}>↑</button>
              <button class="icon-button todo-order-button" data-action="move-todo-down" type="button" title="${t('moveTodoDown')}" aria-label="${t('moveTodoDown')}" ${todoIndex === project.todos.length - 1 ? 'disabled' : ''}>↓</button>
            </span>
            <button class="icon-button danger todo-delete" data-action="delete-todo" type="button" title="${t('deleteTodo')}" aria-label="${t('deleteTodo')}">×</button>
          </div>`).join('');

        return `<article class="project-card note-${project.color}" data-project-id="${escapeHtml(project.id)}">
          <div class="card-head">
            <div class="card-toolbar">
              <div class="drag-handle" draggable="true" title="${t('dragSort')}" aria-label="${t('dragSort')}"><span class="grip">•••</span>${t('dragSort')}</div>
              <div class="head-actions">
                <button class="icon-button" data-action="move-left" type="button" title="${t('moveEarlier')}" aria-label="${t('moveEarlier')}" ${index === 0 ? 'disabled' : ''}>←</button>
                <button class="icon-button" data-action="cycle-color" type="button" title="${t('changeColor')}" aria-label="${t('changeColor')}">◐</button>
                <button class="icon-button danger" data-action="clear-todos" type="button" title="${t('clearTodos')}" aria-label="${t('clearTodos')}" ${project.todos.length ? '' : 'disabled'}>⌫</button>
                <button class="icon-button danger" data-action="clear-project" type="button" title="${t('clearProject')}" aria-label="${t('clearProject')}">×</button>
              </div>
            </div>
            <input class="project-title" data-action="edit-project" maxlength="80" value="${escapeHtml(project.name)}" aria-label="${t('projectName')}">
            <div class="project-meta">
              <span class="progress">${project.todos.length ? t('progress', completed, project.todos.length) : t('noTodos')}</span>
              <select class="priority-select" data-action="project-priority" aria-label="${t('projectPriority')}">${priorityOptions(project.priority, PROJECT_PRIORITIES, 'project')}</select>
            </div>
          </div>
          <div class="card-body">
            <div class="todo-list">${todos}</div>
            <form class="add-todo-form" data-project-id="${escapeHtml(project.id)}">
              <input class="add-todo-input" name="text" maxlength="160" autocomplete="off" placeholder="${t('addNextPlaceholder')}" aria-label="${t('newTodoContent')}" required>
              <select class="todo-priority" name="priority" aria-label="${t('newTodoPriority')}">${priorityOptions('medium', TODO_PRIORITIES, 'todo')}</select>
              <button class="add-todo-button" type="submit" title="${t('addTodo')}" aria-label="${t('addTodo')}">＋</button>
            </form>
          </div>
        </article>`;
      }).join('');
    }

    function findProject(projectId) {
      return state.projects.find(project => project.id === projectId);
    }

    function findTodo(projectId, todoId) {
      return findProject(projectId)?.todos.find(todo => todo.id === todoId);
    }

    function moveTodo(project, todoId, targetIndex) {
      const from = project.todos.findIndex(todo => todo.id === todoId);
      const to = Math.max(0, Math.min(targetIndex, project.todos.length - 1));
      if (from < 0 || from === to) return;
      const [moved] = project.todos.splice(from, 1);
      project.todos.splice(to, 0, moved);
      render();
      scheduleSave();
      showToast(t('todoOrderUpdated'));
    }

    function scheduleSave() {
      setSaveStatus('saving', 'waitingSave');
      clearTimeout(saveTimer);
      saveTimer = setTimeout(saveState, 350);
    }

    function saveState() {
      const snapshot = JSON.stringify(state);
      setSaveStatus('saving', 'saving');
      saveQueue = saveQueue.then(async () => {
        const response = await fetch('/api/state', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: snapshot
        });
        if (!response.ok) throw new Error('save failed');
        setSaveStatus('', 'saved', new Date());
      }).catch(() => {
        setSaveStatus('error', 'saveFailed');
      });
    }

    async function loadState() {
      try {
        const response = await fetch('/api/state');
        if (!response.ok) throw new Error('load failed');
        state = normalizeState(await response.json());
        render();
        setSaveStatus('', 'cacheLoaded');
      } catch (_) {
        render();
        setSaveStatus('error', 'loadFailed');
      }
    }

    function openModal() {
      projectForm.reset();
      modal.hidden = false;
      requestAnimationFrame(() => projectName.focus());
    }

    function closeModal() { modal.hidden = true; }

    languageButton.addEventListener('click', () => {
      currentLanguage = currentLanguage === 'zh' ? 'en' : 'zh';
      try { localStorage.setItem('flowboard_language', currentLanguage); } catch (_) {}
      applyLanguage();
    });

    clearAllButton.addEventListener('click', () => {
      if (!state.projects.length || !confirm(t('confirmClearAll'))) return;
      state.projects = [];
      render();
      scheduleSave();
      showToast(t('allCleared'));
    });

    document.getElementById('addProjectButton').addEventListener('click', openModal);
    document.getElementById('cancelModal').addEventListener('click', closeModal);
    modal.addEventListener('click', event => { if (event.target === modal) closeModal(); });
    document.addEventListener('keydown', event => { if (event.key === 'Escape' && !modal.hidden) closeModal(); });

    projectForm.addEventListener('submit', event => {
      event.preventDefault();
      const form = new FormData(projectForm);
      const name = String(form.get('name') || '').trim();
      if (!name) return;
      state.projects.push({
        id: id('project'), name,
        color: String(form.get('color') || 'yellow'),
        priority: String(form.get('priority') || 'medium'),
        todos: []
      });
      closeModal();
      render();
      scheduleSave();
      showToast(t('projectAdded'));
    });

    board.addEventListener('submit', event => {
      const form = event.target.closest('.add-todo-form');
      if (!form) return;
      event.preventDefault();
      const project = findProject(form.dataset.projectId);
      const data = new FormData(form);
      const text = String(data.get('text') || '').trim();
      if (!project || !text) return;
      project.todos.push({ id: id('todo'), text, priority: String(data.get('priority') || 'medium'), completed: false });
      render();
      scheduleSave();
      const nextInput = board.querySelector(`.add-todo-form[data-project-id="${CSS.escape(project.id)}"] input[name="text"]`);
      nextInput?.focus();
    });

    board.addEventListener('click', event => {
      const actionNode = event.target.closest('[data-action]');
      if (!actionNode) return;
      const card = actionNode.closest('.project-card');
      const todoNode = actionNode.closest('.todo-item');
      const projectId = card?.dataset.projectId;
      const todoId = todoNode?.dataset.todoId;
      const project = findProject(projectId);
      const action = actionNode.dataset.action;

      if (action === 'move-todo-up' && project && todoId) {
        const from = project.todos.findIndex(todo => todo.id === todoId);
        moveTodo(project, todoId, from - 1);
      } else if (action === 'move-todo-down' && project && todoId) {
        const from = project.todos.findIndex(todo => todo.id === todoId);
        moveTodo(project, todoId, from + 1);
      } else if (action === 'clear-project' && project) {
        if (!confirm(t('confirmClearProject', project.name))) return;
        state.projects = state.projects.filter(item => item.id !== projectId);
        render(); scheduleSave(); showToast(t('projectCleared'));
      } else if (action === 'clear-todos' && project && project.todos.length) {
        if (!confirm(t('confirmClearTodos', project.name))) return;
        project.todos = [];
        render(); scheduleSave(); showToast(t('todosCleared'));
      } else if (action === 'delete-todo' && project) {
        project.todos = project.todos.filter(todo => todo.id !== todoId);
        render(); scheduleSave();
      } else if (action === 'cycle-color' && project) {
        project.color = COLORS[(COLORS.indexOf(project.color) + 1) % COLORS.length];
        render(); scheduleSave();
      } else if (action === 'move-left' && project) {
        const from = state.projects.findIndex(item => item.id === projectId);
        if (from > 0) {
          [state.projects[from - 1], state.projects[from]] = [state.projects[from], state.projects[from - 1]];
          render(); scheduleSave();
        }
      }
    });

    board.addEventListener('change', event => {
      const node = event.target;
      const action = node.dataset.action;
      const card = node.closest('.project-card');
      const todoNode = node.closest('.todo-item');
      const project = findProject(card?.dataset.projectId);
      const todo = findTodo(card?.dataset.projectId, todoNode?.dataset.todoId);
      if (action === 'toggle-todo' && todo) {
        todo.completed = node.checked;
        render(); scheduleSave();
      } else if (action === 'edit-project' && project) {
        const value = node.value.trim();
        project.name = value || t('untitledProject');
        render(); scheduleSave();
      } else if (action === 'project-priority' && project) {
        project.priority = node.value;
        scheduleSave();
      } else if (action === 'edit-todo' && todo) {
        const value = node.value.trim();
        todo.text = value || t('untitledTodo');
        render(); scheduleSave();
      } else if (action === 'todo-priority' && todo) {
        todo.priority = node.value;
        todoNode.dataset.priority = node.value;
        scheduleSave();
      }
    });

    board.addEventListener('dragstart', event => {
      const todoHandle = event.target.closest('.todo-drag-handle');
      if (todoHandle) {
        const todoNode = todoHandle.closest('.todo-item');
        draggedTodo = { projectId: todoNode.dataset.projectId, todoId: todoNode.dataset.todoId };
        draggedProjectId = null;
        todoNode.classList.add('todo-dragging');
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', `todo:${draggedTodo.todoId}`);
        return;
      }

      const handle = event.target.closest('.drag-handle');
      if (!handle) return;
      const card = handle.closest('.project-card');
      draggedProjectId = card.dataset.projectId;
      draggedTodo = null;
      card.classList.add('dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', draggedProjectId);
    });

    board.addEventListener('dragover', event => {
      if (draggedTodo) {
        const todoNode = event.target.closest('.todo-item');
        if (!todoNode || todoNode.dataset.projectId !== draggedTodo.projectId || todoNode.dataset.todoId === draggedTodo.todoId) return;
        event.preventDefault();
        board.querySelectorAll('.todo-drag-over').forEach(node => node.classList.remove('todo-drag-over'));
        todoNode.classList.add('todo-drag-over');
        event.dataTransfer.dropEffect = 'move';
        return;
      }

      const card = event.target.closest('.project-card');
      if (!card || card.dataset.projectId === draggedProjectId) return;
      event.preventDefault();
      board.querySelectorAll('.drag-over').forEach(node => node.classList.remove('drag-over'));
      card.classList.add('drag-over');
      event.dataTransfer.dropEffect = 'move';
    });

    board.addEventListener('drop', event => {
      if (draggedTodo) {
        const todoNode = event.target.closest('.todo-item');
        if (!todoNode || todoNode.dataset.projectId !== draggedTodo.projectId || todoNode.dataset.todoId === draggedTodo.todoId) return;
        event.preventDefault();
        const project = findProject(draggedTodo.projectId);
        const targetIndex = project.todos.findIndex(todo => todo.id === todoNode.dataset.todoId);
        const todoId = draggedTodo.todoId;
        draggedTodo = null;
        moveTodo(project, todoId, targetIndex);
        return;
      }

      const card = event.target.closest('.project-card');
      if (!card || !draggedProjectId || card.dataset.projectId === draggedProjectId) return;
      event.preventDefault();
      const from = state.projects.findIndex(project => project.id === draggedProjectId);
      const to = state.projects.findIndex(project => project.id === card.dataset.projectId);
      const [moved] = state.projects.splice(from, 1);
      state.projects.splice(to, 0, moved);
      draggedProjectId = null;
      render(); scheduleSave(); showToast(t('orderUpdated'));
    });

    board.addEventListener('dragend', () => {
      draggedProjectId = null;
      draggedTodo = null;
      board.querySelectorAll('.dragging, .drag-over, .todo-dragging, .todo-drag-over').forEach(node => node.classList.remove('dragging', 'drag-over', 'todo-dragging', 'todo-drag-over'));
    });

    applyLanguage();
    loadState();
  </script>
</body>
</html>
'''


def empty_state() -> dict[str, Any]:
    return {"version": 1, "projects": []}


def load_state() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return empty_state()
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("projects"), list):
            raise ValueError("invalid data shape")
        return data
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = DATA_FILE.with_name(f"flowboard_data.broken-{stamp}.json")
        try:
            DATA_FILE.replace(backup)
        except OSError:
            pass
        print(f"Could not read the data file. Starting with empty data; the original was backed up as {backup.name}: {exc}")
        return empty_state()


def save_state(data: dict[str, Any]) -> None:
    temp_file = DATA_FILE.with_suffix(".json.tmp")
    encoded = json.dumps(data, ensure_ascii=False, indent=2)
    temp_file.write_text(encoded + "\n", encoding="utf-8")
    os.replace(temp_file, DATA_FILE)


class FlowBoardHandler(BaseHTTPRequestHandler):
    server_version = "FlowBoard/1.0"

    def _send_bytes(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send_bytes(body, "application/json; charset=utf-8", status)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self._send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/state":
            with DATA_LOCK:
                self._send_json(load_state())
        elif path == "/favicon.ico":
            self._send_bytes(b"", "image/x-icon", HTTPStatus.NO_CONTENT)
        else:
            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/state":
            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json({"error": "invalid content length"}, HTTPStatus.BAD_REQUEST)
            return

        if length <= 0 or length > MAX_BODY_BYTES:
            self._send_json({"error": "invalid request size"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return

        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("projects"), list):
                raise ValueError("state must contain a projects list")
            with DATA_LOCK:
                save_state(data)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, OSError) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self._send_json({"ok": True})

    def log_message(self, format_string: str, *args: Any) -> None:
        if args and str(args[1]).startswith("4"):
            super().log_message(format_string, *args)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the local FlowBoard project flow board")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=0, help="Port to use; 0 selects an available port automatically (default: 0)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser automatically")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        server = ThreadingHTTPServer((args.host, args.port), FlowBoardHandler)
    except OSError as exc:
        raise SystemExit(f"Could not start FlowBoard: {exc}") from exc

    port = server.server_address[1]
    browser_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    url = f"http://{browser_host}:{port}"
    print("\nFlowBoard is running")
    print(f"Open: {url}")
    print(f"Data file: {DATA_FILE}")
    print("Press Ctrl+C to stop\n")

    if not args.no_browser:
        threading.Timer(0.35, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nFlowBoard stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
