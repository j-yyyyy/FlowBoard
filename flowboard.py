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
  <meta name="theme-color" content="#fafaf9">
  <title>FlowBoard · Project Flow Board</title>
  <style>
    :root {
      --ink: #1c1c1e;
      --muted: #737376;
      --paper: #fafaf9;
      --paper-deep: #efefed;
      --line: #dededb;
      --accent: #ee6c4d;
      --white: #ffffff;
      --shadow: 0 8px 32px rgba(0, 0, 0, .05);
      --radius: 8px;
    }

    * { box-sizing: border-box; }

    html { min-height: 100%; background: var(--paper); }

    body {
      min-height: 100vh;
      margin: 0;
      color: var(--ink);
      font-family: "Helvetica Neue", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: var(--paper);
      -webkit-font-smoothing: antialiased;
    }

    button, input, select { font: inherit; }
    button, select { cursor: pointer; }

    button:focus-visible, input:focus-visible, select:focus-visible {
      outline: 3px solid rgba(69, 123, 157, .35);
      outline-offset: 2px;
    }

    .app-shell { width: min(1600px, 100%); margin: 0 auto; padding: 30px 48px 64px; }

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
      width: 32px;
      height: 32px;
      border-radius: 7px;
      background: var(--ink);
      color: var(--white);
      font-weight: 900;
      font-size: 19px;
    }

    .brand-copy h1 { margin: 0; font-size: 22px; font-weight: 650; letter-spacing: -.055em; }
    .brand-copy p { margin: 5px 0 0; color: var(--muted); font-size: 11px; }

    .save-status {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }

    .save-dot { width: 6px; height: 6px; border-radius: 50%; background: #649377; }
    .save-status.saving .save-dot { background: #dc9f3c; animation: pulse 1s infinite; }
    .save-status.error .save-dot { background: #c94f4f; }

    .topbar-actions { display: flex; align-items: center; gap: 15px; }

    .language-button {
      min-width: 48px;
      height: 34px;
      padding: 0 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: transparent;
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
      padding: 40px 0 28px;
    }

    .hero-meta { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.7; }
    .board-heading { margin: 0 0 8px; font-size: 30px; font-weight: 600; letter-spacing: -.055em; line-height: 1.15; }

    .hero-actions { display: flex; align-items: center; gap: 12px; }

    .primary-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-height: 38px;
      padding: 0 18px;
      border: 0;
      border-radius: 7px;
      background: var(--ink);
      color: white;
      font-size: 13px;
      font-weight: 650;
      box-shadow: none;
      transition: transform .15s, box-shadow .15s;
    }

    .primary-button:hover { transform: translateY(-1px); background: #363638; }
    .primary-button:active { transform: translateY(1px); box-shadow: none; }
    .primary-button .plus { font-size: 22px; line-height: 1; }

    .clear-all-button {
      min-height: 38px;
      padding: 0 16px;
      border: 1px solid transparent;
      border-radius: 7px;
      background: transparent;
      color: var(--muted);
      font-size: 13px;
      font-weight: 600;
    }

    .clear-all-button:hover:not(:disabled) { background: rgba(174, 54, 54, .10); }
    .clear-all-button:disabled, .icon-button:disabled { cursor: not-allowed; opacity: .38; }

    .workspace {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 300px;
      align-items: start;
      gap: 40px;
    }

    .board {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      align-items: start;
      gap: 0;
    }

    .priority-panel {
      position: sticky;
      top: 24px;
      max-height: calc(100vh - 48px);
      overflow: auto;
      padding: 22px 0 0 26px;
      border: 0;
      border-top: 1px solid var(--ink);
      border-left: 1px solid var(--line);
      border-radius: 0;
      background: transparent;
      box-shadow: none;
      scrollbar-width: thin;
      scrollbar-color: #d4dbe3 transparent;
    }

    .priority-panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
    .priority-panel h2 { margin: 0; font-size: 20px; font-weight: 600; letter-spacing: -.035em; }
    .priority-panel-count { flex: 0 0 auto; padding: 4px 0 0 8px; color: var(--muted); font-size: 12px; font-weight: 500; font-variant-numeric: tabular-nums; }
    .priority-panel-description { margin: 10px 0 16px; color: var(--muted); font-size: 11px; line-height: 1.7; }
    .priority-list { display: grid; gap: 0; }

    .priority-item {
      display: grid;
      grid-template-columns: 24px minmax(0, 1fr);
      align-items: start;
      gap: 9px 10px;
      padding: 17px 0 15px;
      border: 0;
      border-top: 1px solid var(--line);
      border-radius: 0;
      background: transparent;
      transition: opacity .15s, box-shadow .15s, transform .15s;
    }

    .priority-item.priority-dragging { opacity: .38; }
    .priority-item.priority-drag-over { box-shadow: inset 0 2px 0 rgba(37,35,31,.45); transform: translateY(1px); }
    .priority-item:hover { background: #f2f2f0; }
    .priority-rank { padding-top: 2px; color: #969695; font-size: 12px; font-weight: 400; font-variant-numeric: tabular-nums; }
    .priority-item:first-child .priority-rank { color: var(--ink); }
    .priority-item-main { min-width: 0; }
    .priority-item-text { overflow-wrap: anywhere; color: #456174; font-size: 13px; font-weight: 500; line-height: 1.6; }
    .priority-item[data-priority="urgent"] .priority-item-text { color: #b63f3f; font-weight: 750; }
    .priority-item[data-priority="high"] .priority-item-text { color: #a85e24; }
    .priority-item[data-priority="low"] .priority-item-text { color: #696f6c; font-weight: 550; }
    .priority-item-project { overflow-wrap: anywhere; margin-top: 5px; color: var(--muted); font-size: 11px; line-height: 1.5; }
    .priority-item-project::before { content: ""; display: inline-block; width: 7px; height: 7px; margin-right: 6px; border-radius: 2px; background: var(--note-accent); }
    .priority-item-actions { grid-column: 2; display: flex; gap: 4px; align-items: center; }
    .priority-item .todo-priority { width: 60px; margin-right: auto; text-align: left; }
    .priority-drag-handle { cursor: grab; }
    .priority-drag-handle:active { cursor: grabbing; }
    .priority-empty { padding: 24px 10px; border: 1px dashed rgba(63,56,46,.20); border-radius: 12px; color: var(--muted); font-size: 13px; line-height: 1.5; text-align: center; }

    .project-card {
      display: grid;
      grid-template-columns: minmax(150px, .38fr) minmax(0, 1fr);
      gap: 28px;
      position: relative;
      min-width: 0;
      padding: 24px 0 28px;
      border: 0;
      border-top: 1px solid var(--line);
      border-radius: 0;
      background: transparent;
      box-shadow: none;
      transition: transform .18s, box-shadow .18s, opacity .18s;
    }

    .project-card:first-child { border-top-color: var(--ink); }
    .project-card.dragging { opacity: .42; transform: scale(.98); }
    .project-card.drag-over { box-shadow: 0 0 0 4px rgba(37, 35, 31, .22), var(--shadow); }

    .note-yellow { --note: #e9dba8; --note-soft: #fff9e8; --note-accent: #c29a37; }
    .note-blue { --note: #bfd8ed; --note-soft: #eff7ff; --note-accent: #5b92c1; }
    .note-green { --note: #bfdcc9; --note-soft: #f0f8f2; --note-accent: #609477; }
    .note-rose { --note: #edc6ce; --note-soft: #fff2f4; --note-accent: #c47c8d; }
    .note-lilac { --note: #d4c8e8; --note-soft: #f6f2fd; --note-accent: #9780bd; }

    .card-head { min-width: 0; padding: 0; }
    .card-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 24px; }
    .project-index { display: inline-flex; align-items: center; gap: 8px; color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
    .project-index::before { content: ""; width: 16px; height: 3px; background: var(--note-accent); }
    .drag-label { display: none; }

    .drag-handle {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 4px 6px 4px 2px;
      border: 0;
      background: transparent;
      color: #737d88;
      font-size: 11px;
      font-weight: 500;
      cursor: grab;
      user-select: none;
    }

    .drag-handle:active { cursor: grabbing; }
    .grip { font-size: 17px; letter-spacing: -4px; transform: rotate(90deg); }
    .head-actions { display: flex; align-items: center; gap: 1px; }

    .icon-button {
      display: grid;
      place-items: center;
      width: 24px;
      height: 24px;
      padding: 0;
      border: 0;
      border-radius: 7px;
      background: transparent;
      color: #8b8b8d;
      transition: background .15s, color .15s;
    }

    .icon-button:hover { background: #eaeae7; color: var(--ink); }
    .icon-button.danger:hover { background: rgba(174,54,54,.13); color: #9e3131; }

    .project-title {
      width: 100%;
      margin-top: 12px;
      padding: 1px 0 5px;
      border: 0;
      border-bottom: 1px solid transparent;
      outline: 0;
      background: transparent;
      color: var(--ink);
      font-size: 20px;
      font-weight: 600;
      letter-spacing: -.04em;
    }

    .project-title:hover, .project-title:focus { border-bottom-color: rgba(37,35,31,.25); }

    .project-meta { display: flex; align-items: flex-start; flex-direction: column; gap: 12px; margin-top: 8px; }
    .progress { color: var(--muted); font-size: 11px; font-weight: 400; font-variant-numeric: tabular-nums; }

    .priority-select, .todo-priority {
      appearance: none;
      border: 1px solid transparent;
      border-radius: 5px;
      background: transparent;
      color: var(--muted);
      font-size: 12px;
      font-weight: 400;
      text-align: center;
    }

    .priority-select { min-height: 29px; padding: 0 26px 0 10px; background-image: linear-gradient(45deg, transparent 50%, #5d574f 50%), linear-gradient(135deg, #5d574f 50%, transparent 50%); background-position: calc(100% - 12px) 12px, calc(100% - 8px) 12px; background-size: 4px 4px; background-repeat: no-repeat; }

    .priority-select { background-color: #efefed; }
    .todo-priority:hover, .todo-priority:focus { background: #ececea; }
    .card-body { min-width: 0; padding: 0; }
    .todo-list { display: grid; gap: 0; min-height: 8px; }

    .todo-item {
      display: grid;
      grid-template-columns: 12px 18px minmax(0, 1fr) 56px 44px 20px;
      align-items: center;
      gap: 6px;
      min-height: 45px;
      padding: 8px 2px;
      border-radius: 5px;
      background: transparent;
    }

    .todo-item:hover, .todo-item:focus-within { background: #f0f0ed; }
    .todo-item > .todo-drag-handle { grid-column: 1; grid-row: 1; }
    .todo-item > .todo-check { grid-column: 2; grid-row: 1; }
    .todo-item > .todo-text { grid-column: 3; grid-row: 1; width: 100%; }
    .todo-item > .todo-priority { grid-column: 4; grid-row: 1; }
    .todo-item > .todo-order-actions { grid-column: 5; grid-row: 1; justify-self: end; }
    .todo-item > .todo-delete { grid-column: 6; grid-row: 1; width: 20px; }
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
      border: 1px solid #b4b4b6;
      border-radius: 50%;
      background: rgba(255,255,255,.80);
      cursor: pointer;
    }

    .todo-check::before { content: "✓"; color: white; font-size: 13px; font-weight: 900; transform: scale(0); transition: transform .12s; }
    .todo-check:checked { border-color: #8c8c8d; background: #8c8c8d; }
    .todo-check:checked::before { transform: scale(1); }

    .todo-text {
      min-width: 0;
      padding: 3px 2px;
      border: 0;
      border-bottom: 1px solid transparent;
      background: transparent;
      color: #486f9a;
      font-size: 13px;
      line-height: 1.35;
    }

    .todo-text:hover, .todo-text:focus { border-bottom-color: rgba(37,35,31,.18); }
    .todo-item[data-priority="urgent"] .todo-text { color: #a4443c; font-weight: 550; }
    .todo-item[data-priority="high"] .todo-text { color: #826242; font-weight: 500; }
    .todo-item[data-priority="medium"] .todo-text { color: #456174; }
    .todo-item[data-priority="low"] .todo-text { color: #696f6c; }
    .todo-item.completed { background: transparent; }
    .todo-item.completed .todo-text { color: #7d8792 !important; text-decoration: line-through; text-decoration-thickness: 1px; }

    .todo-priority { width: 56px; min-height: 26px; padding: 0 3px; font-size: 11px; }
    .todo-order-actions { display: flex; gap: 2px; }
    .todo-order-button { width: 21px; height: 26px; border-radius: 5px; font-size: 11px; }
    .todo-delete, .todo-order-actions, .todo-drag-handle { opacity: .28; transition: opacity .15s; }
    .todo-item:hover .todo-order-actions, .todo-item:focus-within .todo-order-actions, .todo-item:hover .todo-drag-handle, .todo-item:focus-within .todo-drag-handle { opacity: 1; }
    .todo-item:hover .todo-delete, .todo-delete:focus-visible { opacity: 1; }

    .add-todo-form {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 64px 34px;
      gap: 7px;
      margin-top: 8px;
      padding: 9px 0 0;
      border-top: 1px solid #ebebe8;
      align-items: center;
    }

    .add-todo-input {
      min-width: 0;
      height: 35px;
      padding: 0 10px;
      border: 1px solid transparent;
      border-radius: 5px;
      background: transparent;
      color: var(--ink);
      font-size: 12px;
    }

    .add-todo-input::placeholder { color: #929293; }
    .add-todo-input:focus { background: white; border-color: var(--line); }
    .add-todo-button { width: 30px; height: 30px; border: 1px solid var(--line); border-radius: 50%; background: transparent; color: var(--ink); font-size: 18px; }
    .add-todo-button:hover { background: var(--ink); color: white; }

    .empty-state {
      grid-column: 1 / -1;
      display: grid;
      place-items: center;
      min-height: 340px;
      padding: 40px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgba(255,255,255,.55);
      text-align: center;
    }

    .empty-note { display: grid; align-content: center; width: min(280px, 100%); min-height: 150px; padding: 26px 0; }
    .empty-note strong { display: block; font-size: 19px; line-height: 1.4; }
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
      border-radius: 14px;
      background: var(--white);
      box-shadow: 0 28px 80px rgba(30,27,22,.30);
    }

    .modal h3 { margin: 0; font-size: 23px; letter-spacing: -.025em; }
    .modal p { margin: 7px 0 21px; color: var(--muted); font-size: 14px; }
    .field { display: grid; gap: 7px; margin-top: 15px; }
    .field label { color: var(--muted); font-size: 12px; font-weight: 500; }
    .field input, .field select { width: 100%; height: 43px; padding: 0 12px; border: 1px solid #d8d2c8; border-radius: 11px; background: white; color: var(--ink); }

    .color-picker { display: flex; gap: 10px; }
    .color-choice { position: relative; }
    .color-choice input { position: absolute; opacity: 0; pointer-events: none; }
    .color-swatch { display: block; width: 37px; height: 37px; border: 2px solid white; border-radius: 11px; box-shadow: 0 0 0 1px rgba(37,35,31,.17); cursor: pointer; }
    .color-choice input:checked + .color-swatch { box-shadow: 0 0 0 3px var(--ink); transform: rotate(-5deg); }
    .color-choice input:focus-visible + .color-swatch { outline: 3px solid rgba(69,123,157,.50); outline-offset: 4px; }
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

    @media (max-width: 1200px) {
      .project-card { grid-template-columns: minmax(0, 1fr); gap: 16px; }
      .card-head { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px 20px; }
      .card-toolbar { grid-column: 1 / -1; }
      .project-title { margin-top: 0; }
      .project-meta { margin-top: 0; flex-direction: row; align-items: center; }
    }

    @media (max-width: 980px) {
      .workspace { grid-template-columns: 1fr; }
      .priority-panel { position: static; max-height: none; border-left: 0; padding-left: 0; }
    }

    @media (max-width: 720px) {
      .app-shell { padding: 19px 16px 36px; }
      .topbar { align-items: flex-start; }
      .topbar-actions { align-items: flex-end; flex-direction: column-reverse; gap: 9px; }
      .save-status { font-size: 11px; }
      .brand-copy p { display: none; }
      .hero { align-items: stretch; flex-direction: column; gap: 14px; padding: 22px 0; }
      .hero-actions { align-items: stretch; gap: 10px; }
      .hero .primary-button { flex: 1; }
      .hero .clear-all-button { flex: 0 0 auto; }
      .board { grid-template-columns: 1fr; gap: 0; }
      .project-card:hover { transform: none; }
      .todo-delete { opacity: .65; }
      .card-head { padding-inline: 0; grid-template-columns: minmax(0, 1fr); gap: 7px; }
      .card-toolbar { grid-column: 1; }
      .project-meta { justify-content: space-between; }
      .todo-item { grid-template-columns: 12px 18px minmax(0, 1fr) 56px 20px; }
      .todo-item > .todo-delete { grid-column: 5; }
      .todo-item > .todo-order-actions { grid-column: 3 / 5; grid-row: 2; }
      .todo-order-actions, .todo-drag-handle { opacity: .65; }
      .board-heading { font-size: 26px; }
      .workspace { gap: 22px; }
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
        <h2 class="board-heading" id="boardHeading">Projects</h2>
        <p class="hero-meta" id="boardStats">Loading projects…</p>
      </div>
      <div class="hero-actions">
        <button class="clear-all-button" id="clearAllButton" type="button" disabled><span id="clearAllText">Clear all</span></button>
        <button class="primary-button" id="addProjectButton" type="button"><span class="plus">＋</span><span id="addProjectText">Add a project</span></button>
      </div>
    </section>

    <div class="workspace">
      <section class="board" id="board" aria-label="Project note board"></section>
      <aside class="priority-panel" id="priorityPanel" aria-labelledby="priorityPanelTitle">
        <div class="priority-panel-head">
          <h2 id="priorityPanelTitle">Priority order</h2>
          <span class="priority-panel-count" id="priorityPanelCount">0</span>
        </div>
        <p class="priority-panel-description" id="priorityPanelDescription">Drag tasks into the order you want to tackle them.</p>
        <div class="priority-list" id="priorityList"></div>
      </aside>
    </div>
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
        boardLabel: 'Project list',
        boardHeading: 'Projects',
        modalTitle: 'Add a project',
        modalDescription: 'Give it a recognizable name. You can edit it at any time.',
        projectName: 'Project name',
        projectNamePlaceholder: 'e.g. Model A training and evaluation',
        projectPriority: 'Project priority',
        noteColor: 'Project color',
        chooseColor: 'Choose a project color',
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
        changeColor: 'Change project color',
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
        priorityPanelTitle: 'Priority order',
        priorityPanelDescription: 'Drag tasks into the order you want to tackle them.',
        priorityPanelEmpty: 'Add an open task to see it here.',
        priorityProject: name => `Project · ${name}`,
        dragPriorityTodo: 'Drag to rank task',
        movePriorityUp: 'Move task higher',
        movePriorityDown: 'Move task lower',
        priorityOrderUpdated: 'Priority order updated',
        switchLanguage: '切换到中文',
        languageButton: '中文'
      },
      zh: {
        pageTitle: 'FlowBoard · 项目流转板',
        tagline: '让每个流转中的项目，都留在视线里',
        loading: '正在读取…',
        loadingProjects: '载入项目中…',
        addProject: '新建项目',
        clearAll: '清空全部',
        boardLabel: '项目列表',
        boardHeading: '项目',
        modalTitle: '新建项目',
        modalDescription: '先给它一个容易辨认的名字，之后随时都能修改。',
        projectName: '项目名称',
        projectNamePlaceholder: '例如：模型 A 训练与测评',
        projectPriority: '项目重要程度',
        noteColor: '项目标识色',
        chooseColor: '选择项目标识色',
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
        firstProjectHint: '创建第一个项目，安排接下来要做的事。',
        emptyTitle: '还没有项目',
        emptyText: '点击上方按钮添加第一个项目',
        dragSort: '拖动排序',
        moveEarlier: '向前移动',
        changeColor: '更换项目标识色',
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
        projectAdded: '项目已创建',
        confirmClearAll: '确定清空页面中的所有项目和待办吗？此操作无法撤销。',
        allCleared: '已清空全部项目',
        confirmClearProject: name => `确定清空项目“${name}”及其中所有待办吗？项目本身也会被删除。`,
        projectCleared: '已清空项目',
        confirmClearTodos: name => `确定清空项目“${name}”中的全部待办吗？项目本身会保留。`,
        todosCleared: '已清空项目待办',
        orderUpdated: '项目顺序已更新',
        todoOrderUpdated: '待办顺序已更新',
        priorityPanelTitle: '优先级顺序',
        priorityPanelDescription: '拖动待办，排出接下来要处理的先后顺序。',
        priorityPanelEmpty: '添加一条未完成待办后，它会自动出现在这里。',
        priorityProject: name => `项目 · ${name}`,
        dragPriorityTodo: '拖动调整全局优先顺序',
        movePriorityUp: '提高待办顺序',
        movePriorityDown: '降低待办顺序',
        priorityOrderUpdated: '优先级顺序已更新',
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

    let state = { version: 1, projects: [], priorityOrder: [] };
    let saveTimer = null;
    let saveQueue = Promise.resolve();
    let draggedProjectId = null;
    let draggedTodo = null;
    let draggedPriorityTodoId = null;
    let saveStateInfo = { kind: '', key: 'loading', args: [] };

    const board = document.getElementById('board');
    const priorityPanel = document.getElementById('priorityPanel');
    const priorityList = document.getElementById('priorityList');
    const priorityPanelCount = document.getElementById('priorityPanelCount');
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
      document.getElementById('boardHeading').textContent = t('boardHeading');
      document.getElementById('priorityPanelTitle').textContent = t('priorityPanelTitle');
      document.getElementById('priorityPanelDescription').textContent = t('priorityPanelDescription');
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
      const rawProjects = Array.isArray(raw?.projects) ? raw.projects : [];
      const projects = rawProjects.map(project => ({
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
        }));
      const todoIds = projects.flatMap(project => project.todos.map(todo => todo.id));
      const validIds = new Set(todoIds);
      const seen = new Set();
      const savedOrder = Array.isArray(raw?.priorityOrder) ? raw.priorityOrder : [];
      const priorityOrder = savedOrder
        .map(String)
        .filter(todoId => validIds.has(todoId) && !seen.has(todoId) && seen.add(todoId));
      todoIds.forEach(todoId => {
        if (!seen.has(todoId)) priorityOrder.push(todoId);
      });
      return {
        version: 1,
        projects,
        priorityOrder
      };
    }

    function syncPriorityOrder() {
      const todoIds = state.projects.flatMap(project => project.todos.map(todo => todo.id));
      const validIds = new Set(todoIds);
      const seen = new Set();
      state.priorityOrder = (Array.isArray(state.priorityOrder) ? state.priorityOrder : [])
        .filter(todoId => validIds.has(todoId) && !seen.has(todoId) && seen.add(todoId));
      todoIds.forEach(todoId => {
        if (!seen.has(todoId)) state.priorityOrder.push(todoId);
      });
    }

    function priorityItems() {
      const byId = new Map();
      state.projects.forEach(project => {
        project.todos.forEach(todo => byId.set(todo.id, { project, todo }));
      });
      return state.priorityOrder
        .map(todoId => byId.get(todoId))
        .filter(item => item && !item.todo.completed);
    }

    function renderPriorityPanel() {
      const items = priorityItems();
      priorityPanelCount.textContent = String(items.length);
      if (!items.length) {
        priorityList.innerHTML = `<div class="priority-empty">${t('priorityPanelEmpty')}</div>`;
        return;
      }
      priorityList.innerHTML = items.map(({ project, todo }, index) => `
        <div class="priority-item note-${project.color}" draggable="true" data-todo-id="${escapeHtml(todo.id)}" data-priority="${todo.priority}">
          <span class="priority-rank priority-drag-handle" title="${t('dragPriorityTodo')}" aria-hidden="true">${String(index + 1).padStart(2, '0')}</span>
          <div class="priority-item-main" title="${escapeHtml(todo.text)}">
            <div class="priority-item-text">${escapeHtml(todo.text)}</div>
            <div class="priority-item-project">${escapeHtml(t('priorityProject', project.name))}</div>
          </div>
          <div class="priority-item-actions">
            <select class="todo-priority" data-action="priority-todo-priority" aria-label="${t('todoPriority')}">${priorityOptions(todo.priority, TODO_PRIORITIES, 'todo')}</select>
            <button class="icon-button todo-order-button" data-action="move-priority-up" type="button" title="${t('movePriorityUp')}" aria-label="${t('movePriorityUp')}" ${index === 0 ? 'disabled' : ''}>↑</button>
            <button class="icon-button todo-order-button" data-action="move-priority-down" type="button" title="${t('movePriorityDown')}" aria-label="${t('movePriorityDown')}" ${index === items.length - 1 ? 'disabled' : ''}>↓</button>
          </div>
        </div>`).join('');
    }

    function render() {
      syncPriorityOrder();
      renderPriorityPanel();
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
              <div class="drag-handle" draggable="true" title="${t('dragSort')}" aria-label="${t('dragSort')}"><span class="project-index">${String(index + 1).padStart(2, '0')}</span><span class="drag-label">${t('dragSort')}</span></div>
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

    function findTodoById(todoId) {
      for (const project of state.projects) {
        const todo = project.todos.find(item => item.id === todoId);
        if (todo) return todo;
      }
      return null;
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

    function movePriorityTodo(todoId, targetTodoId) {
      if (!todoId || !targetTodoId || todoId === targetTodoId) return;
      const from = state.priorityOrder.indexOf(todoId);
      if (from < 0) return;
      state.priorityOrder.splice(from, 1);
      const to = state.priorityOrder.indexOf(targetTodoId);
      if (to < 0) return;
      state.priorityOrder.splice(to, 0, todoId);
      render();
      scheduleSave();
      showToast(t('priorityOrderUpdated'));
    }

    function movePriorityTodoByStep(todoId, direction) {
      const visibleIds = priorityItems().map(item => item.todo.id);
      const from = visibleIds.indexOf(todoId);
      const target = visibleIds[from + direction];
      if (from < 0 || !target) return;
      const firstIndex = state.priorityOrder.indexOf(todoId);
      const secondIndex = state.priorityOrder.indexOf(target);
      [state.priorityOrder[firstIndex], state.priorityOrder[secondIndex]] = [state.priorityOrder[secondIndex], state.priorityOrder[firstIndex]];
      render();
      scheduleSave();
      showToast(t('priorityOrderUpdated'));
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
      const newTodo = { id: id('todo'), text, priority: String(data.get('priority') || 'medium'), completed: false };
      const firstCompletedIndex = project.todos.findIndex(todo => todo.completed);
      if (firstCompletedIndex === -1) {
        project.todos.push(newTodo);
      } else {
        project.todos.splice(firstCompletedIndex, 0, newTodo);
      }
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
        if (node.checked && project) {
          const completedIndex = project.todos.findIndex(item => item.id === todo.id);
          if (completedIndex >= 0 && completedIndex < project.todos.length - 1) {
            const [completedTodo] = project.todos.splice(completedIndex, 1);
            project.todos.push(completedTodo);
          }
        }
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
        render(); scheduleSave();
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

    priorityPanel.addEventListener('click', event => {
      const actionNode = event.target.closest('[data-action]');
      const item = event.target.closest('.priority-item');
      if (!actionNode || !item) return;
      if (actionNode.dataset.action === 'move-priority-up') {
        movePriorityTodoByStep(item.dataset.todoId, -1);
      } else if (actionNode.dataset.action === 'move-priority-down') {
        movePriorityTodoByStep(item.dataset.todoId, 1);
      }
    });

    priorityPanel.addEventListener('change', event => {
      if (event.target.dataset.action !== 'priority-todo-priority') return;
      const item = event.target.closest('.priority-item');
      const todo = findTodoById(item?.dataset.todoId);
      if (!todo) return;
      todo.priority = event.target.value;
      render();
      scheduleSave();
    });

    priorityPanel.addEventListener('dragstart', event => {
      const item = event.target.closest('.priority-item');
      if (!item) return;
      draggedPriorityTodoId = item.dataset.todoId;
      item.classList.add('priority-dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', `priority:${draggedPriorityTodoId}`);
    });

    priorityPanel.addEventListener('dragover', event => {
      const item = event.target.closest('.priority-item');
      if (!item || !draggedPriorityTodoId || item.dataset.todoId === draggedPriorityTodoId) return;
      event.preventDefault();
      priorityPanel.querySelectorAll('.priority-drag-over').forEach(node => node.classList.remove('priority-drag-over'));
      item.classList.add('priority-drag-over');
      event.dataTransfer.dropEffect = 'move';
    });

    priorityPanel.addEventListener('drop', event => {
      const item = event.target.closest('.priority-item');
      if (!item || !draggedPriorityTodoId || item.dataset.todoId === draggedPriorityTodoId) return;
      event.preventDefault();
      const todoId = draggedPriorityTodoId;
      draggedPriorityTodoId = null;
      movePriorityTodo(todoId, item.dataset.todoId);
    });

    priorityPanel.addEventListener('dragend', () => {
      draggedPriorityTodoId = null;
      priorityPanel.querySelectorAll('.priority-dragging, .priority-drag-over').forEach(node => node.classList.remove('priority-dragging', 'priority-drag-over'));
    });

    applyLanguage();
    loadState();
  </script>
</body>
</html>
'''


def empty_state() -> dict[str, Any]:
    return {"version": 1, "projects": [], "priorityOrder": []}


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
