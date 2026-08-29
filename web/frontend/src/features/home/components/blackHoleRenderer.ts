import {
  Application,
  Geometry,
  Mesh,
  Shader,
  Texture,
  UniformGroup,
} from 'pixi.js'

import { ACADEMIC_ORBIT_SEGMENTS } from '@/i18n/invariantContent'

export type BlackHoleStage = 'dormant' | 'forming' | 'ready'

export interface BlackHoleRendererState {
  stage: BlackHoleStage
  paused: boolean
  reducedMotion: boolean
  dark: boolean
}

export interface BlackHoleRenderer {
  canvas: HTMLCanvasElement
  setState: (state: BlackHoleRendererState) => void
  resize: () => void
  destroy: () => void
}

interface AtlasGlyph {
  u0: number
  v0: number
  u1: number
  v1: number
}

interface StreamDefinition {
  source: [number, number]
  control1: [number, number]
  control2: [number, number]
  approachAngle: number
  orbitOffset: number
  speed: number
  phase: number
  tone: number
  opacity: number
  text: string
}

const GLYPH_VERTEX = `
in vec2 aCorner;
in vec2 aUV;
in vec4 aPathA;
in vec4 aPathB;
in vec4 aMeta;
in vec4 aStyle;

uniform mat3 uProjectionMatrix;
uniform mat3 uWorldTransformMatrix;
uniform mat3 uTransformMatrix;
uniform vec4 uWorldColorAlpha;

uniform vec2 uViewport;
uniform vec2 uCore;
uniform float uCoreRadius;
uniform float uTime;
uniform float uFormation;
uniform float uStreamLimit;
uniform float uPass;
uniform float uMotionScale;

out vec2 vUV;
out float vAlpha;
out float vTone;
out float vFront;
out float vDistance;

vec2 rotatePoint(vec2 point, float angle) {
  float sine = sin(angle);
  float cosine = cos(angle);
  return mat2(cosine, -sine, sine, cosine) * point;
}

vec2 cubicBezier(vec2 p0, vec2 p1, vec2 p2, vec2 p3, float t) {
  float inverse = 1.0 - t;
  return inverse * inverse * inverse * p0
    + 3.0 * inverse * inverse * t * p1
    + 3.0 * inverse * t * t * p2
    + t * t * t * p3;
}

vec2 pathPosition(float progress, vec4 pathA, vec4 pathB) {
  float entryEnd = 0.56;
  vec2 source = pathA.xy * uViewport;
  vec2 control1 = pathA.zw * uViewport;
  vec2 control2 = pathB.xy * uViewport;
  float approachAngle = pathB.z;
  float outerRadius = uCoreRadius * (2.65 + pathB.w);
  vec2 approach = uCore + rotatePoint(
    vec2(cos(approachAngle) * outerRadius, sin(approachAngle) * outerRadius * 0.34),
    0.28
  );

  if (progress < entryEnd) {
    float t = smoothstep(0.0, 1.0, progress / entryEnd);
    return cubicBezier(source, control1, control2, approach, t);
  }

  float orbitProgress = (progress - entryEnd) / (1.0 - entryEnd);
  float angle = approachAngle + orbitProgress * 4.72;
  float radius = mix(outerRadius, uCoreRadius * 1.035, pow(orbitProgress, 0.82));
  vec2 orbit = vec2(cos(angle) * radius, sin(angle) * radius * 0.34);
  return uCore + rotatePoint(orbit, 0.28);
}

void main(void) {
  float baseProgress = aMeta.x;
  float progress = fract(baseProgress + aMeta.z + uTime * aMeta.y * uMotionScale);
  vec2 center = pathPosition(progress, aPathA, aPathB);
  vec2 nextCenter = pathPosition(min(progress + 0.0025, 0.999), aPathA, aPathB);
  vec2 tangent = normalize(nextCenter - center + vec2(0.0001));
  vec2 normal = vec2(-tangent.y, tangent.x);

  float compression = mix(1.14, 0.58, smoothstep(0.28, 1.0, progress));
  float size = aMeta.w * compression;
  vec2 position = center
    + tangent * aCorner.x * size
    + normal * aCorner.y * size;

  float streamVisible = 1.0 - step(uStreamLimit, aStyle.z);
  float reveal = 1.0 - smoothstep(uFormation - 0.035, uFormation + 0.055, baseProgress);
  reveal *= smoothstep(0.035, 0.16, uFormation);
  float edgeFade = smoothstep(0.012, 0.055, progress)
    * (1.0 - smoothstep(0.91, 0.998, progress));

  float orbiting = step(0.56, progress);
  float orbitProgress = clamp((progress - 0.56) / 0.44, 0.0, 1.0);
  float orbitAngle = aPathB.z + orbitProgress * 4.72;
  vFront = orbiting * step(0.0, sin(orbitAngle));
  float passVisible = uPass < 0.5 ? 1.0 - vFront : vFront;

  vUV = aUV;
  vTone = aStyle.x;
  vAlpha = aStyle.w * reveal * edgeFade * streamVisible * passVisible;
  vDistance = length(center - uCore) / max(uCoreRadius, 1.0);

  mat3 matrix = uProjectionMatrix * uWorldTransformMatrix * uTransformMatrix;
  gl_Position = vec4((matrix * vec3(position, 1.0)).xy, 0.0, 1.0);
}
`

const GLYPH_FRAGMENT = `
in vec2 vUV;
in float vAlpha;
in float vTone;
in float vFront;
in float vDistance;

uniform sampler2D uGlyphTexture;
uniform float uTheme;
uniform float uFormation;

out vec4 finalColor;

void main(void) {
  float glyph = texture(uGlyphTexture, vUV).a;
  if (glyph < 0.015 || vAlpha < 0.005) discard;

  vec3 lightInk = vec3(0.10, 0.105, 0.11);
  vec3 darkInk = vec3(0.92, 0.95, 0.97);
  vec3 ink = mix(lightInk, darkInk, uTheme);
  vec3 hot = mix(vec3(0.64, 0.29, 0.12), vec3(1.0, 0.58, 0.23), uTheme);
  vec3 cool = mix(vec3(0.16, 0.43, 0.57), vec3(0.52, 0.83, 1.0), uTheme);
  vec3 color = vTone < 0.5 ? ink : (vTone < 1.5 ? hot : cool);

  float horizonHeat = 1.0 - smoothstep(1.04, 2.35, vDistance);
  color = mix(color, mix(hot, cool, 0.32), horizonHeat * 0.38);
  float alpha = glyph * vAlpha * mix(0.82, 1.0, horizonHeat);
  finalColor = vec4(color * alpha, alpha);
}
`

const CORE_VERTEX = `
in vec2 aPosition;

uniform mat3 uProjectionMatrix;
uniform mat3 uWorldTransformMatrix;
uniform mat3 uTransformMatrix;
uniform vec2 uViewport;

out vec2 vScene;

void main(void) {
  vec2 position = aPosition * uViewport;
  vScene = position;
  mat3 matrix = uProjectionMatrix * uWorldTransformMatrix * uTransformMatrix;
  gl_Position = vec4((matrix * vec3(position, 1.0)).xy, 0.0, 1.0);
}
`

const CORE_FRAGMENT = `
in vec2 vScene;

uniform vec2 uViewport;
uniform vec2 uCore;
uniform float uCoreRadius;
uniform float uTheme;
uniform float uFormation;
uniform float uTime;

out vec4 finalColor;

float hash(vec2 point) {
  return fract(sin(dot(point, vec2(127.1, 311.7))) * 43758.5453123);
}

vec2 rotatePoint(vec2 point, float angle) {
  float sine = sin(angle);
  float cosine = cos(angle);
  return mat2(cosine, -sine, sine, cosine) * point;
}

void main(void) {
  vec2 point = vScene - uCore;
  float distanceToCore = length(point);
  float radius = max(uCoreRadius, 1.0);
  if (distanceToCore > radius * 4.9) discard;

  vec2 diskPoint = rotatePoint(point, -0.28);
  float normalizedRadius = distanceToCore / radius;
  float horizon = 1.0 - smoothstep(0.975, 1.02, normalizedRadius);
  float photon = exp(-pow((normalizedRadius - 1.055) / 0.043, 2.0));
  float outerLens = exp(-pow((normalizedRadius - 1.19) / 0.13, 2.0));

  float warpedY = diskPoint.y
    + sign(diskPoint.y) * radius * 0.018 * pow(abs(diskPoint.x) / radius, 1.5);
  float band = exp(-pow(warpedY / (radius * 0.092), 2.0));
  band *= smoothstep(4.45, 1.08, abs(diskPoint.x) / radius);
  band *= 1.0 - horizon;

  float angle = atan(point.y, point.x);
  float hotArc = photon * smoothstep(-0.25, 0.85, sin(angle + 0.65));
  float striation = 0.72 + 0.28 * sin(diskPoint.x * 0.095 + uTime * 0.22);
  band *= striation;

  vec3 hot = mix(vec3(0.63, 0.27, 0.10), vec3(1.0, 0.56, 0.20), uTheme);
  vec3 cool = mix(vec3(0.24, 0.55, 0.68), vec3(0.62, 0.87, 1.0), uTheme);
  vec3 whiteLight = mix(vec3(0.72, 0.83, 0.85), vec3(0.95, 0.98, 1.0), uTheme);
  vec3 color = vec3(0.0);
  float alpha = 0.0;

  float halo = outerLens * mix(0.13, 0.2, uTheme);
  color += mix(hot, cool, 0.58) * halo;
  alpha += halo;

  color += hot * band * mix(0.14, 0.24, uTheme);
  alpha += band * mix(0.11, 0.19, uTheme);

  color += cool * photon * (0.67 + 0.23 * uTheme);
  color += hot * hotArc * 0.75;
  color += whiteLight * photon * 0.35;
  alpha += photon * 0.93;

  float grain = hash(floor(vScene * 0.72));
  float dust = step(0.993, grain) * (1.0 - smoothstep(1.2, 4.6, normalizedRadius));
  color += mix(cool, hot, hash(vScene * 0.013)) * dust * 0.55;
  alpha += dust * 0.6;

  vec3 core = mix(vec3(0.008, 0.009, 0.012), vec3(0.001), smoothstep(0.0, 1.0, normalizedRadius));
  color = mix(color, core, horizon);
  alpha = mix(alpha, 1.0, horizon);

  float formationAlpha = smoothstep(0.0, 0.24, uFormation);
  alpha *= formationAlpha;
  color *= formationAlpha;
  finalColor = vec4(color * alpha, alpha);
}
`

function createGlyphAtlas() {
  const text = ACADEMIC_ORBIT_SEGMENTS.flat().join(' · ')
  const characters = [
    ...new Set(Array.from(text).filter((character) => character !== ' ')),
  ]
  const cellSize = 72
  const columns = 16
  const rows = Math.ceil(characters.length / columns)
  const canvas = document.createElement('canvas')
  canvas.width = columns * cellSize
  canvas.height = rows * cellSize
  const context = canvas.getContext('2d')

  if (!context) {
    throw new Error('Canvas 2D is unavailable for the glyph atlas.')
  }

  context.clearRect(0, 0, canvas.width, canvas.height)
  context.font = '400 42px "IBM Plex Mono", monospace'
  context.textAlign = 'center'
  context.textBaseline = 'middle'
  context.fillStyle = '#ffffff'
  context.shadowColor = 'rgba(255,255,255,.42)'
  context.shadowBlur = 5

  const glyphs = new Map<string, AtlasGlyph>()
  characters.forEach((character, index) => {
    const column = index % columns
    const row = Math.floor(index / columns)
    const x = column * cellSize
    const y = row * cellSize
    context.fillText(character, x + cellSize / 2, y + cellSize / 2 + 1)
    glyphs.set(character, {
      u0: x / canvas.width,
      v0: y / canvas.height,
      u1: (x + cellSize) / canvas.width,
      v1: (y + cellSize) / canvas.height,
    })
  })

  return { canvas, glyphs }
}

function makeStreamDefinitions(): StreamDefinition[] {
  const texts = ACADEMIC_ORBIT_SEGMENTS.map((segments) =>
    `${segments.join('  ·  ')}  ·  `.repeat(2),
  )
  const streams: StreamDefinition[] = []

  for (let index = 0; index < 7; index += 1) {
    const spread = index - 3
    streams.push({
      source: [-0.13 + index * 0.012, 0.84 + index * 0.052],
      control1: [0.015 + index * 0.012, 0.77 + index * 0.025],
      control2: [0.12 + index * 0.014, 0.59 + index * 0.012],
      approachAngle: 2.34 + spread * 0.055,
      orbitOffset: spread * 0.055,
      speed: 0.031 + (index % 3) * 0.003,
      phase: index * 0.061,
      tone: index % 4 === 0 ? 1 : index % 5 === 0 ? 2 : 0,
      opacity: 0.72 + (index % 3) * 0.08,
      text: texts[index % texts.length] ?? '',
    })
  }

  for (let index = 0; index < 5; index += 1) {
    const spread = index - 2
    streams.push({
      source: [-0.12 + index * 0.025, -0.16 + index * 0.045],
      control1: [0.01 + index * 0.018, 0.04 + index * 0.035],
      control2: [0.12 + index * 0.016, 0.17 + index * 0.025],
      approachAngle: 3.88 + spread * 0.07,
      orbitOffset: spread * 0.07,
      speed: 0.034 + (index % 2) * 0.004,
      phase: 0.17 + index * 0.073,
      tone: index % 3 === 0 ? 2 : index % 4 === 0 ? 1 : 0,
      opacity: 0.68 + (index % 2) * 0.1,
      text: texts[(index + 2) % texts.length] ?? '',
    })
  }

  for (let index = 0; index < 4; index += 1) {
    const spread = index - 1.5
    streams.push({
      source: [0.83 + index * 0.09, 1.12 - index * 0.025],
      control1: [0.75 + index * 0.025, 0.98 - index * 0.018],
      control2: [0.49 + index * 0.018, 0.73 - index * 0.018],
      approachAngle: 0.72 + spread * 0.075,
      orbitOffset: spread * 0.075,
      speed: 0.029 + index * 0.003,
      phase: 0.31 + index * 0.081,
      tone: index % 2 === 0 ? 1 : 0,
      opacity: 0.62 + index * 0.06,
      text: texts[(index + 1) % texts.length] ?? '',
    })
  }

  return streams
}

function createGlyphGeometry(glyphs: Map<string, AtlasGlyph>) {
  const corners: number[] = []
  const uvs: number[] = []
  const pathA: number[] = []
  const pathB: number[] = []
  const metadata: number[] = []
  const styles: number[] = []
  const indices: number[] = []
  const streams = makeStreamDefinitions()
  // Keep all three entry directions represented when mobile quality hides four streams.
  const qualityRanks = [0, 1, 2, 3, 4, 12, 13, 5, 6, 7, 8, 14, 9, 10, 11, 15]
  const cornerValues = [
    [-0.5, -0.5],
    [0.5, -0.5],
    [0.5, 0.5],
    [-0.5, 0.5],
  ]

  let glyphIndex = 0
  streams.forEach((stream, streamIndex) => {
    const characters = Array.from(stream.text).slice(0, 94)
    characters.forEach((character, characterIndex) => {
      const glyph = glyphs.get(character)
      if (!glyph) return

      const progress = characterIndex / Math.max(characters.length, 1)
      const fontSize = 27 + (streamIndex % 4) * 1.35
      const glyphUvs = [
        [glyph.u0, glyph.v0],
        [glyph.u1, glyph.v0],
        [glyph.u1, glyph.v1],
        [glyph.u0, glyph.v1],
      ]

      cornerValues.forEach((corner, vertexIndex) => {
        corners.push(corner[0] ?? 0, corner[1] ?? 0)
        const uv = glyphUvs[vertexIndex] ?? [0, 0]
        uvs.push(uv[0] ?? 0, uv[1] ?? 0)
        pathA.push(...stream.source, ...stream.control1)
        pathB.push(...stream.control2, stream.approachAngle, stream.orbitOffset)
        metadata.push(progress, stream.speed, stream.phase, fontSize)
        styles.push(
          stream.tone,
          streamIndex,
          qualityRanks[streamIndex] ?? streamIndex,
          stream.opacity,
        )
      })

      const vertexOffset = glyphIndex * 4
      indices.push(
        vertexOffset,
        vertexOffset + 1,
        vertexOffset + 2,
        vertexOffset,
        vertexOffset + 2,
        vertexOffset + 3,
      )
      glyphIndex += 1
    })
  })

  return new Geometry({
    label: 'academic-character-streams',
    attributes: {
      aCorner: { buffer: new Float32Array(corners), format: 'float32x2' },
      aUV: { buffer: new Float32Array(uvs), format: 'float32x2' },
      aPathA: { buffer: new Float32Array(pathA), format: 'float32x4' },
      aPathB: { buffer: new Float32Array(pathB), format: 'float32x4' },
      aMeta: { buffer: new Float32Array(metadata), format: 'float32x4' },
      aStyle: { buffer: new Float32Array(styles), format: 'float32x4' },
    },
    indexBuffer: new Uint32Array(indices),
  })
}

function createCoreGeometry() {
  return new Geometry({
    label: 'event-horizon-plane',
    attributes: {
      aPosition: {
        buffer: new Float32Array([0, 0, 1, 0, 1, 1, 0, 1]),
        format: 'float32x2',
      },
    },
    indexBuffer: new Uint32Array([0, 1, 2, 0, 2, 3]),
  })
}

function makeUniforms(pass = 0) {
  return new UniformGroup({
    uViewport: { value: new Float32Array([1, 1]), type: 'vec2<f32>' },
    uCore: { value: new Float32Array([1, 1]), type: 'vec2<f32>' },
    uCoreRadius: { value: 100, type: 'f32' },
    uTime: { value: 0, type: 'f32' },
    uFormation: { value: 0, type: 'f32' },
    uStreamLimit: { value: 16, type: 'f32' },
    uPass: { value: pass, type: 'f32' },
    uMotionScale: { value: 1, type: 'f32' },
    uTheme: { value: 0, type: 'f32' },
  })
}

export async function createBlackHoleRenderer(
  host: HTMLElement,
  initialState: BlackHoleRendererState,
): Promise<BlackHoleRenderer> {
  await document.fonts?.load('400 42px "IBM Plex Mono"')

  const application = new Application()
  const resolution = Math.min(window.devicePixelRatio || 1, 1.5)
  await application.init({
    preference: 'webgl',
    powerPreference: 'high-performance',
    resizeTo: host,
    resolution,
    autoDensity: true,
    antialias: false,
    backgroundAlpha: 0,
  })

  application.canvas.className = 'black-hole__canvas'
  application.canvas.setAttribute('aria-hidden', 'true')
  host.appendChild(application.canvas)

  const atlas = createGlyphAtlas()
  const glyphTexture = Texture.from(atlas.canvas)
  const glyphGeometry = createGlyphGeometry(atlas.glyphs)
  const coreGeometry = createCoreGeometry()
  const backUniforms = makeUniforms(0)
  const frontUniforms = makeUniforms(1)
  const coreUniforms = makeUniforms(0)

  const makeGlyphShader = (uniforms: UniformGroup) =>
    Shader.from({
      gl: {
        name: 'academic-character-flow',
        vertex: GLYPH_VERTEX,
        fragment: GLYPH_FRAGMENT,
      },
      resources: {
        blackHoleUniforms: uniforms,
        uGlyphTexture: glyphTexture.source,
      },
    })

  const coreShader = Shader.from({
    gl: {
      name: 'event-horizon',
      vertex: CORE_VERTEX,
      fragment: CORE_FRAGMENT,
    },
    resources: { blackHoleUniforms: coreUniforms },
  })

  const backMesh = new Mesh({
    geometry: glyphGeometry,
    shader: makeGlyphShader(backUniforms),
  })
  const coreMesh = new Mesh({ geometry: coreGeometry, shader: coreShader })
  const frontMesh = new Mesh({
    geometry: glyphGeometry,
    shader: makeGlyphShader(frontUniforms),
  })
  application.stage.addChild(backMesh, coreMesh, frontMesh)

  let state = initialState
  let elapsed = 0
  let formation = state.stage === 'ready' ? 1 : 0
  let destroyed = false

  const resize = () => {
    if (destroyed) return
    const width = Math.max(application.screen.width, 1)
    const height = Math.max(application.screen.height, 1)
    const mobile = width < 768 || (width <= 1024 && height <= 500)
    const core = new Float32Array([
      width * (mobile ? 0.42 : 0.24),
      height * (mobile ? 0.43 : 0.38),
    ])
    const viewport = new Float32Array([width, height])
    const radius = Math.min(width, height) * (mobile ? 0.15 : 0.115)

    ;[backUniforms, frontUniforms, coreUniforms].forEach((uniforms) => {
      uniforms.uniforms.uViewport = viewport
      uniforms.uniforms.uCore = core
      uniforms.uniforms.uCoreRadius = radius
      uniforms.uniforms.uStreamLimit = mobile ? 12 : 16
    })
  }

  const syncUniforms = () => {
    const theme = state.dark ? 1 : 0
    const motionScale = state.reducedMotion ? 0 : 1
    ;[backUniforms, frontUniforms, coreUniforms].forEach((uniforms) => {
      uniforms.uniforms.uTime = elapsed
      uniforms.uniforms.uFormation = formation
      uniforms.uniforms.uTheme = theme
      uniforms.uniforms.uMotionScale = motionScale
    })
  }

  const tick = (ticker: { deltaMS: number }) => {
    if (state.paused || destroyed) return
    const deltaSeconds = Math.min(ticker.deltaMS / 1000, 0.05)
    if (!state.reducedMotion && state.stage === 'ready') {
      elapsed += deltaSeconds * 0.6
    }
    const formationTarget = state.stage === 'dormant' ? 0 : 1
    const formationSpeed = state.stage === 'dormant' ? 4.2 : 1.15
    formation +=
      Math.sign(formationTarget - formation) *
      Math.min(
        Math.abs(formationTarget - formation),
        deltaSeconds * formationSpeed,
      )
    syncUniforms()
  }

  const setState = (nextState: BlackHoleRendererState) => {
    const enteringReady = state.stage !== 'ready' && nextState.stage === 'ready'
    state = nextState
    if (enteringReady && nextState.reducedMotion) formation = 1
    syncUniforms()

    if (state.paused || state.reducedMotion) {
      application.ticker.stop()
      application.render()
    } else {
      application.ticker.start()
    }
  }

  resize()
  syncUniforms()
  application.ticker.add(tick)
  setState(initialState)

  return {
    canvas: application.canvas,
    setState,
    resize,
    destroy() {
      destroyed = true
      application.ticker.remove(tick)
      application.destroy(
        { removeView: true },
        { children: true, texture: true, textureSource: true },
      )
    },
  }
}
