"use client"

import { useEffect, useRef } from "react"

const VERTEX_SHADER = `
attribute vec2 a_position;
void main() {
  gl_Position = vec4(a_position, 0.0, 1.0);
}
`

const FRAGMENT_SHADER = `
precision mediump float;
uniform float u_time;
uniform vec2 u_resolution;

// Smooth noise hash
vec2 hash2(vec2 p) {
  p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
  return fract(sin(p) * 43758.5453);
}

// Value noise
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);

  float a = dot(hash2(i), f - vec2(0.0, 0.0));
  float b = dot(hash2(i + vec2(1.0, 0.0)), f - vec2(1.0, 0.0));
  float c = dot(hash2(i + vec2(0.0, 1.0)), f - vec2(0.0, 1.0));
  float d = dot(hash2(i + vec2(1.0, 1.0)), f - vec2(1.0, 1.0));

  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y) * 0.5 + 0.5;
}

float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 4; i++) {
    v += a * noise(p);
    p = p * 2.1 + vec2(1.7, 9.2);
    a *= 0.5;
  }
  return v;
}

void main() {
  vec2 uv = gl_FragCoord.xy / u_resolution;
  float aspect = u_resolution.x / u_resolution.y;
  vec2 st = vec2(uv.x * aspect, uv.y);

  float t = u_time * 0.06;

  float n = fbm(st * 1.8 + vec2(t * 0.4, t * 0.3));
  float n2 = fbm(st * 2.4 + vec2(-t * 0.3, t * 0.5) + n * 0.6);

  // Subtle blue/cyan tones for the dark background
  vec3 col1 = vec3(0.0, 0.05, 0.12);   // deep navy
  vec3 col2 = vec3(0.0, 0.12, 0.24);   // mid navy-blue
  vec3 col3 = vec3(0.0, 0.08, 0.18);   // muted blue

  vec3 color = mix(col1, col2, n);
  color = mix(color, col3, n2 * 0.5);

  // Vignette — keep edges darkest
  float vignette = 1.0 - smoothstep(0.35, 1.0, length(uv - 0.5) * 1.6);
  color *= vignette;

  // Very low overall opacity: 0.04–0.07 range
  float alpha = 0.055;
  gl_FragColor = vec4(color, alpha);
}
`

function compileShader(gl: WebGLRenderingContext, type: number, src: string): WebGLShader | null {
  const shader = gl.createShader(type)
  if (!shader) return null
  gl.shaderSource(shader, src)
  gl.compileShader(shader)
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    gl.deleteShader(shader)
    return null
  }
  return shader
}

function createProgram(
  gl: WebGLRenderingContext,
  vert: string,
  frag: string,
): WebGLProgram | null {
  const vs = compileShader(gl, gl.VERTEX_SHADER, vert)
  const fs = compileShader(gl, gl.FRAGMENT_SHADER, frag)
  if (!vs || !fs) return null

  const program = gl.createProgram()
  if (!program) return null

  gl.attachShader(program, vs)
  gl.attachShader(program, fs)
  gl.linkProgram(program)

  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    gl.deleteProgram(program)
    return null
  }
  return program
}

export function ShaderBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const gl = canvas.getContext("webgl", {
      alpha: true,
      premultipliedAlpha: false,
      antialias: false,
    })
    if (!gl) return

    const program = createProgram(gl, VERTEX_SHADER, FRAGMENT_SHADER)
    if (!program) return

    // Full-screen quad
    const posBuffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, posBuffer)
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
      gl.STATIC_DRAW,
    )

    const posLoc = gl.getAttribLocation(program, "a_position")
    const timeLoc = gl.getUniformLocation(program, "u_time")
    const resLoc = gl.getUniformLocation(program, "u_resolution")

    let rafId = 0
    const startTime = performance.now()

    function resize() {
      if (!canvas || !gl) return
      const dpr = Math.min(window.devicePixelRatio ?? 1, 1.5)
      const w = Math.floor(canvas.offsetWidth * dpr)
      const h = Math.floor(canvas.offsetHeight * dpr)
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w
        canvas.height = h
        gl.viewport(0, 0, w, h)
      }
    }

    function render(now: number) {
      if (!gl || !program || !canvas) return
      resize()

      const elapsed = (now - startTime) * 0.001

      gl.enable(gl.BLEND)
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA)
      gl.clearColor(0, 0, 0, 0)
      gl.clear(gl.COLOR_BUFFER_BIT)

      gl.useProgram(program)

      gl.bindBuffer(gl.ARRAY_BUFFER, posBuffer)
      gl.enableVertexAttribArray(posLoc)
      gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0)

      gl.uniform1f(timeLoc, elapsed)
      gl.uniform2f(resLoc, canvas.width, canvas.height)

      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)

      rafId = requestAnimationFrame(render)
    }

    rafId = requestAnimationFrame(render)

    const ro = new ResizeObserver(() => resize())
    ro.observe(canvas)

    return () => {
      cancelAnimationFrame(rafId)
      ro.disconnect()
      gl.deleteBuffer(posBuffer)
      gl.deleteProgram(program)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      data-testid="shader-background"
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 h-full w-full"
      style={{ zIndex: 0 }}
    />
  )
}
