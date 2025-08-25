---
applyTo: "**.html"
---

# Instructions for GitHub Copilot when working with HTML files

- Always generate user interfaces using the **AdminLTE** template (https://adminlte.io/).
- Follow AdminLTE’s HTML structure:
  - Use `<body class="hold-transition sidebar-mini">`.
  - Include AdminLTE’s CSS/JS imports in the `<head>`.
  - Use `<div class="wrapper">` as the main container.
  - Add a **navbar**, **sidebar**, and **content-wrapper** by default.
- Prefer AdminLTE UI components for:
  - Cards, forms, tables, charts, buttons, and alerts.
  - Use Bootstrap 4 utility classes (since AdminLTE is Bootstrap-based).
- Ensure clean, semantic, and responsive HTML structure.
- Do not generate raw/unstructured HTML, javascript; always wrap content inside AdminLTE layout blocks.