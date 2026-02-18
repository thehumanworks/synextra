import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AnimatedInput } from "./animated-input"

describe("AnimatedInput", () => {
  it("renders an input with the given value", () => {
    render(<AnimatedInput value="hello" onChange={() => undefined} />)
    expect(screen.getByRole("textbox")).toHaveValue("hello")
  })

  it("applies opacity-70 class when disabled", () => {
    render(<AnimatedInput value="" onChange={() => undefined} disabled />)
    const container = screen.getByTestId("animated-input-container")
    expect(container.className).toContain("opacity-70")
  })

  it("does not apply opacity class when enabled", () => {
    render(<AnimatedInput value="" onChange={() => undefined} disabled={false} />)
    const container = screen.getByTestId("animated-input-container")
    expect(container.className).not.toContain("opacity-50")
    expect(container.className).not.toContain("opacity-70")
  })

  it("applies placeholder-stone-400 class to the input", () => {
    render(<AnimatedInput value="" onChange={() => undefined} />)
    const input = screen.getByRole("textbox")
    expect(input.className).toContain("placeholder-stone-400")
  })

  it("input text color is text-stone-100", () => {
    render(<AnimatedInput value="" onChange={() => undefined} />)
    const input = screen.getByRole("textbox")
    expect(input.className).toContain("text-stone-100")
  })

  it("applies aria-label when provided", () => {
    render(<AnimatedInput value="" onChange={() => undefined} aria-label="My message" />)
    expect(screen.getByRole("textbox", { name: "My message" })).toBeInTheDocument()
  })

  it("is disabled when disabled prop is true", () => {
    render(<AnimatedInput value="" onChange={() => undefined} disabled />)
    expect(screen.getByRole("textbox")).toBeDisabled()
  })

  it("container remains visible (border not hidden) when disabled", () => {
    render(<AnimatedInput value="" onChange={() => undefined} disabled />)
    const container = screen.getByTestId("animated-input-container")
    // opacity-70 is visible enough; must not be opacity-0
    expect(container.className).not.toContain("opacity-0")
    expect(container.className).toContain("border")
  })
})
