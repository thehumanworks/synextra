import { render, screen, act } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ShaderBackground } from "./shader-background"

// WebGL is not available in jsdom – stub it so the component degrades gracefully.
function stubWebGL() {
  const mockGl = {
    createShader: vi.fn(() => ({})),
    shaderSource: vi.fn(),
    compileShader: vi.fn(),
    getShaderParameter: vi.fn(() => true),
    deleteShader: vi.fn(),
    createProgram: vi.fn(() => ({})),
    attachShader: vi.fn(),
    linkProgram: vi.fn(),
    getProgramParameter: vi.fn(() => true),
    deleteProgram: vi.fn(),
    createBuffer: vi.fn(() => ({})),
    bindBuffer: vi.fn(),
    bufferData: vi.fn(),
    getAttribLocation: vi.fn(() => 0),
    getUniformLocation: vi.fn(() => ({})),
    enable: vi.fn(),
    blendFunc: vi.fn(),
    clearColor: vi.fn(),
    clear: vi.fn(),
    useProgram: vi.fn(),
    enableVertexAttribArray: vi.fn(),
    vertexAttribPointer: vi.fn(),
    uniform1f: vi.fn(),
    uniform2f: vi.fn(),
    drawArrays: vi.fn(),
    viewport: vi.fn(),
    deleteBuffer: vi.fn(),
    VERTEX_SHADER: 35633,
    FRAGMENT_SHADER: 35632,
    COMPILE_STATUS: 35713,
    LINK_STATUS: 35714,
    ARRAY_BUFFER: 34962,
    STATIC_DRAW: 35044,
    TRIANGLE_STRIP: 5,
    BLEND: 3042,
    SRC_ALPHA: 770,
    ONE_MINUS_SRC_ALPHA: 771,
    COLOR_BUFFER_BIT: 16384,
    FLOAT: 5126,
  }

  HTMLCanvasElement.prototype.getContext = vi.fn((type) => {
    if (type === "webgl") return mockGl
    return null
  }) as typeof HTMLCanvasElement.prototype.getContext

  return mockGl
}

// ResizeObserver is not implemented in jsdom
class MockResizeObserver {
  observe = vi.fn()
  disconnect = vi.fn()
  unobserve = vi.fn()
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  constructor(_cb: ResizeObserverCallback) {}
  // end stub
}

describe("ShaderBackground", () => {
  let rafSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    // Stub ResizeObserver before component mounts
    vi.stubGlobal("ResizeObserver", MockResizeObserver)

    rafSpy = vi.spyOn(window, "requestAnimationFrame").mockImplementation(() => {
      // Don't actually invoke the callback to avoid infinite render loops
      return 1
    })
    vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => undefined)
    stubWebGL()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("renders a canvas element", () => {
    render(<ShaderBackground />)
    const canvas = screen.getByTestId("shader-background")
    expect(canvas.tagName).toBe("CANVAS")
  })

  it("canvas is aria-hidden", () => {
    render(<ShaderBackground />)
    const canvas = screen.getByTestId("shader-background")
    expect(canvas).toHaveAttribute("aria-hidden", "true")
  })

  it("canvas has pointer-events-none so it doesn't intercept clicks", () => {
    render(<ShaderBackground />)
    const canvas = screen.getByTestId("shader-background")
    expect(canvas.className).toContain("pointer-events-none")
  })

  it("canvas is positioned fixed to cover the full viewport", () => {
    render(<ShaderBackground />)
    const canvas = screen.getByTestId("shader-background")
    expect(canvas.className).toContain("fixed")
    expect(canvas.className).toContain("inset-0")
  })

  it("schedules an animation frame on mount", () => {
    render(<ShaderBackground />)
    expect(rafSpy).toHaveBeenCalled()
  })

  it("cancels animation frame on unmount", () => {
    const cancelSpy = vi.spyOn(window, "cancelAnimationFrame")
    const { unmount } = render(<ShaderBackground />)
    act(() => { unmount() })
    expect(cancelSpy).toHaveBeenCalled()
  })
})
