# Theming & CSS Variables

## CSS Import Options

```tsx
import '@xyflow/react/dist/style.css';  // Full styles (nodes, handles, controls themed)
// OR
import '@xyflow/react/dist/base.css';   // Minimal base — bring your own theme
```

## Dark Mode

Built-in since v12. Use the `colorMode` prop:

```tsx
<ReactFlow colorMode="dark" />   // 'light' | 'dark' | 'system'
```

`colorMode="system"` reads `prefers-color-scheme`. React Flow adds `.dark` or `.light` class to `.react-flow`.

## CSS Variable System

Three-tier fallback: `var(--xy-prop-props, var(--xy-prop, var(--xy-prop-default)))`.

- `-props` suffix: set by component from React props (highest priority)
- no suffix: **your override** — set on `.react-flow` or ancestor
- `-default` suffix: baked-in fallback

**Override at theme level:**

```css
.react-flow {
  --xy-edge-stroke: #0ea5e9;
  --xy-node-background-color: #1e1e1e;
  --xy-node-border: 1px solid #3c3c3c;
}
```

## Complete Variable Reference

### Edges

| Variable | Controls | Light Default | Dark Default |
|----------|----------|---------------|--------------|
| `--xy-edge-stroke` | Edge path color | `#b1b1b7` | `#3e3e3e` |
| `--xy-edge-stroke-width` | Edge width | `1` | `1` |
| `--xy-edge-stroke-selected` | Selected edge color | `#555` | `#727272` |
| `--xy-connectionline-stroke` | Drag connection line | `#b1b1b7` | `#b1b1b7` |
| `--xy-connectionline-stroke-width` | Connection line width | `1` | `1` |

### Nodes

| Variable | Controls | Light Default | Dark Default |
|----------|----------|---------------|--------------|
| `--xy-node-color` | Text color | `inherit` | `#f8f8f8` |
| `--xy-node-border` | Border | `1px solid #1a192b` | `1px solid #3c3c3c` |
| `--xy-node-background-color` | Background | `#fff` | `#1e1e1e` |
| `--xy-node-group-background-color` | Group node bg | `rgba(240,240,240,0.25)` | same |
| `--xy-node-boxshadow-hover` | Hover shadow | `0 1px 4px 1px rgba(0,0,0,0.08)` | `rgba(255,255,255,0.08)` |
| `--xy-node-boxshadow-selected` | Selected shadow | `0 0 0 0.5px #1a192b` | `0 0 0 0.5px #999` |
| `--xy-node-border-radius` | Corner radius | `3px` | `3px` |

### Handles

| Variable | Controls | Light Default | Dark Default |
|----------|----------|---------------|--------------|
| `--xy-handle-background-color` | Handle fill | `#1a192b` | `#bebebe` |
| `--xy-handle-border-color` | Handle border | `#fff` | `#1e1e1e` |

### Background

| Variable | Controls | Light Default | Dark Default |
|----------|----------|---------------|--------------|
| `--xy-background-color` | Canvas bg | `transparent` | `#141414` |
| `--xy-background-pattern-color` | Pattern override (all) | — | — |
| `--xy-background-pattern-dots-color` | Dot color | `#91919a` | `#777` |
| `--xy-background-pattern-lines-color` | Line color | `#eee` | `#777` |
| `--xy-background-pattern-cross-color` | Cross color | `#e2e2e2` | `#777` |

### MiniMap

| Variable | Controls |
|----------|----------|
| `--xy-minimap-background-color` | Minimap bg |
| `--xy-minimap-mask-background-color` | Viewport mask fill |
| `--xy-minimap-mask-stroke-color` | Mask border |
| `--xy-minimap-node-background-color` | Node color in minimap |
| `--xy-minimap-node-stroke-color` | Node border in minimap |

### Controls

| Variable | Controls |
|----------|----------|
| `--xy-controls-button-background-color` | Button bg |
| `--xy-controls-button-background-color-hover` | Button hover bg |
| `--xy-controls-button-color` | Icon color |
| `--xy-controls-button-color-hover` | Icon hover color |
| `--xy-controls-button-border-color` | Divider border |
| `--xy-controls-box-shadow` | Panel shadow |

### Other

| Variable | Controls |
|----------|----------|
| `--xy-edge-label-background-color` | Edge label bg |
| `--xy-edge-label-color` | Edge label text |
| `--xy-selection-background-color` | Selection box fill |
| `--xy-selection-border` | Selection box border |
| `--xy-resize-background-color` | Resize handle color |
| `--xy-attribution-background-color` | Attribution bg |

## CSS Class Targets

| Class | Element |
|-------|---------|
| `.react-flow` | Root container |
| `.react-flow.dark` / `.react-flow.light` | Color mode class |
| `.react-flow__node` | All nodes |
| `.react-flow__node-default` | Default built-in node |
| `.react-flow__node-input` | Input built-in node |
| `.react-flow__node-output` | Output built-in node |
| `.react-flow__node-group` | Group node |
| `.react-flow__edge` | All edges |
| `.react-flow__edge.selected` | Selected edge |
| `.react-flow__edge.animated` | Animated edge |
| `.react-flow__edge-path` | SVG edge path |
| `.react-flow__handle` | Connection handles |
| `.react-flow__background` | Background component |
| `.react-flow__minimap` | MiniMap component |
| `.react-flow__controls` | Controls component |
| `.react-flow__panel` | Panel component |
| `.react-flow__pane` | Canvas pane |
| `.react-flow__selection` | Selection rectangle |
| `.react-flow__edgelabel-renderer` | Edge label portal |

## Custom Animated Edge CSS

```css
@keyframes dashdraw {
  from { stroke-dashoffset: 10; }
}

.react-flow__edge.animated path {
  stroke-dasharray: 5;
  animation: dashdraw 0.5s linear infinite;
}
```

## Dark Theme Example (Full Override)

```css
.react-flow {
  --xy-background-color: #0a0a0a;
  --xy-background-pattern-dots-color: #333;
  --xy-edge-stroke: #57534e;
  --xy-edge-stroke-selected: #0ea5e9;
  --xy-node-color: #e7e5e4;
  --xy-node-border: 2px solid #57534e;
  --xy-node-background-color: #171717;
  --xy-node-boxshadow-selected: 0 0 0 2px #0ea5e9;
  --xy-handle-background-color: #57534e;
  --xy-handle-border-color: #171717;
  --xy-controls-button-background-color: #1e1e1e;
  --xy-controls-button-background-color-hover: #2b2b2b;
  --xy-controls-button-color: #e7e5e4;
  --xy-controls-button-border-color: #3c3c3c;
  --xy-minimap-background-color: #0a0a0a;
  --xy-minimap-mask-background-color: rgba(0, 0, 0, 0.7);
  --xy-minimap-node-background-color: #57534e;
  --xy-resize-background-color: #0ea5e9;
}
```
