"use client"

import { useEffect, useMemo, useRef, useState } from "react"

interface AnimatedInputProps {
  value: string
  onChange: (value: string) => void
  onSubmit?: () => void
  disabled?: boolean
  placeholders?: string[]
  id?: string
  "aria-label"?: string
}

export function AnimatedInput({
  value,
  onChange,
  onSubmit,
  disabled = false,
  placeholders: customPlaceholders,
  id,
  "aria-label": ariaLabel = "Message input",
}: AnimatedInputProps) {
  const [isFocused, setIsFocused] = useState(false)
  const [placeholderIndex, setPlaceholderIndex] = useState(0)
  const [displayedText, setDisplayedText] = useState("")
  const [isTyping, setIsTyping] = useState(true)

  const placeholders = useMemo(
    () =>
      customPlaceholders ?? [
        "What does this document cover?",
        "Summarize the key findings…",
        "Find references to…",
        "Explain the methodology…",
      ],
    [customPlaceholders],
  )

  const CHAR_DELAY = 75
  const IDLE_DELAY_AFTER_FINISH = 2200

  const intervalRef = useRef<number | null>(null)
  const timeoutRef = useRef<number | null>(null)

  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }

    const current = placeholders[placeholderIndex]
    if (!current) {
      setDisplayedText("")
      setIsTyping(false)
      return
    }

    const chars = Array.from(current)
    setDisplayedText("")
    setIsTyping(true)

    let charIndex = 0

    intervalRef.current = window.setInterval(() => {
      if (charIndex < chars.length) {
        const next = chars.slice(0, charIndex + 1).join("")
        setDisplayedText(next)
        charIndex += 1
      } else {
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
        setIsTyping(false)

        timeoutRef.current = window.setTimeout(() => {
          setPlaceholderIndex((prev) => (prev + 1) % placeholders.length)
        }, IDLE_DELAY_AFTER_FINISH)
      }
    }, CHAR_DELAY)

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
    }
  }, [placeholderIndex, placeholders])

  return (
    <div
      className={`flex items-center gap-4 rounded-2xl border bg-zinc-950 p-4 transition-all duration-300 ease-out ${
        isFocused
          ? "border-stone-500 shadow-[0_0_20px_rgba(168,162,158,0.08)]"
          : "border-zinc-800"
      } ${disabled ? "pointer-events-none opacity-50" : ""}`}
    >
      <div className="relative flex-shrink-0">
        <div className="h-12 w-12 overflow-hidden rounded-full">
          <img
            src="https://media.giphy.com/media/26gsuUjoEBmLrNBxC/giphy.gif"
            alt=""
            className="h-full w-full object-cover"
          />
        </div>
      </div>

      <div className="h-8 w-px bg-zinc-700" />

      <div className="flex-1">
        <input
          id={id}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              onSubmit?.()
            }
          }}
          disabled={disabled}
          placeholder={`${displayedText}${isTyping ? "|" : ""}`}
          aria-label={ariaLabel}
          className="w-full border-none bg-transparent text-sm font-light leading-relaxed text-stone-100 placeholder-stone-500 outline-none"
        />
      </div>
    </div>
  )
}
