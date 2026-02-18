import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"

// Mock heavy child components so we isolate the page layout tests
vi.mock("@/components/document-chat-workspace", () => ({
  DocumentChatWorkspace: () => <div data-testid="workspace" />,
}))

vi.mock("@/components/ui/shader-background", () => ({
  ShaderBackground: () => <canvas data-testid="shader-bg" />,
}))

// Must import page AFTER mocks are set up
import Page from "./page"

describe("Home page", () => {
  beforeEach(() => {
    vi.spyOn(window, "requestAnimationFrame").mockImplementation(() => 1)
    vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => undefined)
  })

  it("renders the Synextra title", () => {
    render(<Page />)
    expect(screen.getByRole("heading", { name: /synextra/i })).toBeInTheDocument()
  })

  it("title element uses the electric gradient CSS class", () => {
    render(<Page />)
    const heading = screen.getByRole("heading", { name: /synextra/i })
    expect(heading.className).toContain("title-gradient-text")
  })

  it("subtitle is present", () => {
    render(<Page />)
    expect(screen.getByText(/chat with your documents/i)).toBeInTheDocument()
  })

  it("main element has responsive padding classes", () => {
    render(<Page />)
    const main = screen.getByRole("main")
    expect(main.className).toContain("px-3")
    expect(main.className).toContain("sm:px-4")
    expect(main.className).toContain("md:px-6")
  })

  it("renders the ShaderBackground component", () => {
    render(<Page />)
    expect(screen.getByTestId("shader-bg")).toBeInTheDocument()
  })

  it("renders the DocumentChatWorkspace component", () => {
    render(<Page />)
    expect(screen.getByTestId("workspace")).toBeInTheDocument()
  })
})
