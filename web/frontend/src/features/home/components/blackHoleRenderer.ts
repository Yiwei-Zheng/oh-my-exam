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
  qualityRank: number
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
uniform float uSettled;
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
  float entryEnd = 0.80;
  vec2 source = pathA.xy * uViewport;
  vec2 control1 = pathA.zw * uViewport;
  vec2 control2 = pathB.xy * uViewport;
  float approachAngle = pathB.z;
  float outerRadius = uCoreRadius * (1.45 + pathB.w);
  vec2 approach = uCore + rotatePoint(
    vec2(cos(approachAngle) * outerRadius, sin(approachAngle) * outerRadius * 0.52),
    -0.34
  );

  if (progress < entryEnd) {
    float t = smoothstep(0.0, 1.0, progress / entryEnd);
    return cubicBezier(source, control1, control2, approach, t);
  }

  float orbitProgress = (progress - entryEnd) / (1.0 - entryEnd);
  float angle = approachAngle + orbitProgress * 2.72;
  float radius = mix(outerRadius, uCoreRadius * 0.985, pow(orbitProgress, 0.72));
  vec2 orbit = vec2(cos(angle) * radius, sin(angle) * radius * 0.52);
  return uCore + rotatePoint(orbit, -0.34);
}

void main(void) {
  float baseProgress = aMeta.x;
  float infallProgress = fract(baseProgress + aMeta.z + uTime * aMeta.y * uMotionScale);
  float diskProgress = 0.80 + fract(
    baseProgress + aMeta.z + uTime * aMeta.y * 0.22 * uMotionScale
  ) * 0.195;
  float progress = mix(infallProgress, diskProgress, uSettled);
  vec2 center = pathPosition(progress, aPathA, aPathB);
  vec2 nextCenter = pathPosition(min(progress + 0.0025, 0.999), aPathA, aPathB);
  vec2 tangent = normalize(nextCenter - center + vec2(0.0001));
  tangent *= aPathA.x > 0.5 ? -1.0 : 1.0;
  vec2 normal = vec2(-tangent.y, tangent.x);

  float compression = mix(1.18, 0.48, smoothstep(0.18, 1.0, progress));
  float size = aMeta.w * compression;
  vec2 position = center
    + tangent * aCorner.x * size
    + normal * aCorner.y * size;

  float streamVisible = 1.0 - step(uStreamLimit, aStyle.z);
  float reveal = 1.0 - smoothstep(uFormation - 0.035, uFormation + 0.055, baseProgress);
  reveal *= smoothstep(0.18, 0.34, uFormation);
  float edgeFade = smoothstep(0.012, 0.055, progress)
    * (1.0 - smoothstep(0.91, 0.998, progress));

  vec2 diskPosition = rotatePoint(center - uCore, 0.34);
  vFront = step(0.0, diskPosition.y);
  float passVisible = uPass < 0.5 ? 1.0 - vFront : vFront;

  vec2 viewportPosition = center / uViewport;
  float titleX = smoothstep(0.54, 0.59, viewportPosition.x)
    * (1.0 - smoothstep(0.88, 0.93, viewportPosition.x));
  float titleY = smoothstep(0.37, 0.42, viewportPosition.y)
    * (1.0 - smoothstep(0.61, 0.66, viewportPosition.y));
  float titleProtection = titleX * titleY;

  vUV = aUV;
  vTone = aStyle.x;
  vAlpha = aStyle.w * reveal * edgeFade * streamVisible * passVisible
    * (1.0 - titleProtection * 0.96);
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

  vec3 paperInk = vec3(0.075, 0.082, 0.09);
  vec3 starlight = vec3(0.91, 0.94, 0.96);
  vec3 ink = mix(paperInk, starlight, uTheme);
  vec3 hot = vec3(1.0, 0.47, 0.16);
  vec3 color = mix(ink, starlight, (1.0 - smoothstep(1.8, 4.7, vDistance)) * (1.0 - uTheme));

  float horizonHeat = 1.0 - smoothstep(1.01, 2.15, vDistance);
  color = mix(color, hot, horizonHeat * (0.54 + vTone * 0.12));
  color += vec3(1.0, 0.82, 0.58) * pow(horizonHeat, 3.0) * 0.32;
  float alpha = glyph * vAlpha * mix(0.76, 1.0, horizonHeat);
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

float noise(vec2 point) {
  vec2 cell = floor(point);
  vec2 local = fract(point);
  local = local * local * (3.0 - 2.0 * local);
  return mix(
    mix(hash(cell), hash(cell + vec2(1.0, 0.0)), local.x),
    mix(hash(cell + vec2(0.0, 1.0)), hash(cell + vec2(1.0)), local.x),
    local.y
  );
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
  if (distanceToCore > radius * 6.8) discard;

  vec2 diskPoint = rotatePoint(point, 0.34);
  vec2 horizonPoint = vec2(diskPoint.x, diskPoint.y / 0.79);
  float normalizedRadius = length(horizonPoint) / radius;
  float angle = atan(horizonPoint.y, horizonPoint.x);
  float horizon = 1.0 - smoothstep(0.965, 1.015, normalizedRadius);
  float photon = exp(-pow((normalizedRadius - 1.035) / 0.026, 2.0));
  float lensRadius = length(vec2(diskPoint.x, diskPoint.y / 0.78)) / radius;
  float lensRing = exp(-pow((lensRadius - 1.38) / 0.15, 2.0));
  float outerLensRing = exp(-pow((lensRadius - 1.67) / 0.23, 2.0));

  float directWidth = radius * (0.068 + 0.024 * abs(diskPoint.x) / radius);
  float directDisk = exp(-pow(diskPoint.y / directWidth, 2.0));
  directDisk *= smoothstep(5.8, 1.04, abs(diskPoint.x) / radius);
  directDisk *= 1.0 - horizon;

  float farSide = (lensRing + outerLensRing * 0.72) * smoothstep(-0.22, 0.55, -sin(angle));
  float nearSide = (lensRing + outerLensRing * 0.58) * smoothstep(-0.40, 0.72, sin(angle)) * 0.62;
  float lensDisk = (farSide + nearSide) * (1.0 - horizon);

  float radialGrain = noise(vec2(angle * 18.0, normalizedRadius * 31.0 - uTime * 0.18));
  float fineLines = 0.56 + 0.44 * pow(abs(sin(angle * 43.0 + normalizedRadius * 19.0)), 7.0);
  float turbulence = mix(0.48, 1.18, radialGrain) * fineLines;
  directDisk *= turbulence;
  lensDisk *= mix(0.62, 1.22, radialGrain);

  float beaming = 0.03 + 1.36 * pow(smoothstep(-0.42, 0.94, -cos(angle + 0.35)), 2.0);
  float hotCrescent = photon * beaming;

  vec3 ember = vec3(0.84, 0.075, 0.018);
  vec3 hot = vec3(1.0, 0.25, 0.045);
  vec3 gold = vec3(1.0, 0.56, 0.16);
  vec3 whiteLight = vec3(1.0, 0.91, 0.72);
  vec3 color = vec3(0.0);
  float alpha = 0.0;
  float coreFormation = smoothstep(0.0, 0.055, uFormation);
  float diskFormation = smoothstep(0.15, 0.72, uFormation);

  float spaceFalloff = 1.0 - smoothstep(1.1, 6.6, distanceToCore / radius);
  float nebula = noise(vScene * 0.006 + vec2(uTime * 0.006, 0.0));
  float spaceAlpha = spaceFalloff * mix(0.80, 0.14, uTheme) * (0.70 + nebula * 0.30) * coreFormation;
  color += vec3(0.004, 0.006, 0.012) * spaceAlpha;
  alpha += spaceAlpha;

  float diskLight = directDisk * (0.58 + 0.52 * beaming) * diskFormation;
  lensDisk *= diskFormation;
  color += mix(ember, gold, turbulence) * diskLight * 1.18;
  color += mix(hot, whiteLight, farSide) * lensDisk * 0.98;
  alpha += diskLight * 0.82 + lensDisk * 0.76;

  float diffuseGlow = exp(-pow((normalizedRadius - 1.38) / 0.48, 2.0)) * diskFormation;
  color += ember * diffuseGlow * 0.17;
  alpha += diffuseGlow * 0.10;

  color += hot * photon * 0.20 * diskFormation;
  color += whiteLight * hotCrescent * 1.34 * diskFormation;
  alpha += (photon * 0.30 + hotCrescent * 0.74) * diskFormation;

  float starCell = hash(floor(vScene * 0.20));
  float star = step(0.9965, starCell) * pow(hash(floor(vScene * 0.43)), 4.0);
  star *= smoothstep(1.25, 2.0, normalizedRadius) * spaceFalloff * coreFormation;
  color += vec3(0.72, 0.82, 1.0) * star;
  alpha += star * 0.84;

  vec3 core = mix(vec3(0.003, 0.004, 0.008), vec3(0.0), smoothstep(0.0, 1.0, normalizedRadius));
  color = mix(color, core * coreFormation, horizon);
  alpha = mix(alpha, coreFormation, horizon);
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

  for (let index = 0; index < 6; index += 1) {
    const spread = index - 2.5
    streams.push({
      source: [-0.18 + index * 0.025, 0.92 + index * 0.055],
      control1: [-0.02 + index * 0.018, 0.78 + index * 0.032],
      control2: [0.1 + index * 0.016, 0.58 + index * 0.018],
      approachAngle: 2.48 + spread * 0.045,
      orbitOffset: spread * 0.04,
      speed: 0.025 + (index % 3) * 0.0025,
      phase: index * 0.061,
      tone: index % 4 === 0 ? 1 : 0,
      opacity: 0.58 + (index % 3) * 0.07,
      qualityRank: [0, 3, 6, 9, 14, 22][index] ?? index,
      text: texts[index % texts.length] ?? '',
    })
  }

  for (let index = 0; index < 5; index += 1) {
    const spread = index - 2
    streams.push({
      source: [-0.16 + index * 0.032, -0.17 + index * 0.035],
      control1: [-0.02 + index * 0.022, 0.03 + index * 0.028],
      control2: [0.11 + index * 0.017, 0.2 + index * 0.022],
      approachAngle: 3.8 + spread * 0.052,
      orbitOffset: spread * 0.045,
      speed: 0.026 + (index % 2) * 0.003,
      phase: 0.17 + index * 0.073,
      tone: index % 4 === 0 ? 1 : 0,
      opacity: 0.56 + (index % 2) * 0.08,
      qualityRank: [1, 4, 7, 11, 19][index] ?? index,
      text: texts[(index + 2) % texts.length] ?? '',
    })
  }

  const rightQualityRanks = [
    2, 5, 8, 10, 12, 13, 15, 16, 17, 18, 20, 21, 23, 24, 25, 26, 27, 28,
  ]
  for (let index = 0; index < 30; index += 1) {
    const spread = index - 14.5
    const sourceY = -0.2 + index * 0.049
    streams.push({
      source: [1.1 + (index % 3) * 0.035, sourceY],
      control1: [0.83 + (index % 2) * 0.018, 0.02 + index * 0.034],
      control2: [0.49 + Math.abs(spread) * 0.0035, 0.26 + index * 0.0125],
      approachAngle: spread * 0.018,
      orbitOffset: spread * 0.014,
      speed: 0.021 + (index % 4) * 0.002,
      phase: 0.31 + index * 0.081,
      tone: index % 6 === 0 ? 1 : 0,
      opacity: 0.7 + (index % 4) * 0.055,
      qualityRank: rightQualityRanks[index] ?? index + 11,
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
  const cornerValues = [
    [-0.5, -0.5],
    [0.5, -0.5],
    [0.5, 0.5],
    [-0.5, 0.5],
  ]

  let glyphIndex = 0
  streams.forEach((stream, streamIndex) => {
    const characters = Array.from(stream.text).slice(0, 180)
    characters.forEach((character, characterIndex) => {
      const glyph = glyphs.get(character)
      if (!glyph) return

      const progress = characterIndex / Math.max(characters.length, 1)
      const fontSize = 13.5 + (streamIndex % 4) * 0.8
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
          stream.qualityRank,
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
    uSettled: { value: 0, type: 'f32' },
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
  let formationAge = state.stage === 'ready' ? 4.4 : 0
  let settled = state.stage === 'ready' ? 1 : 0
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
    const radius = Math.min(width, height) * (mobile ? 0.185 : 0.145)

    ;[backUniforms, frontUniforms, coreUniforms].forEach((uniforms) => {
      uniforms.uniforms.uViewport = viewport
      uniforms.uniforms.uCore = core
      uniforms.uniforms.uCoreRadius = radius
      uniforms.uniforms.uStreamLimit = mobile ? 17 : 41
    })
  }

  const syncUniforms = () => {
    const theme = state.dark ? 1 : 0
    const motionScale = state.reducedMotion ? 0 : 1
    ;[backUniforms, frontUniforms, coreUniforms].forEach((uniforms) => {
      uniforms.uniforms.uTime = elapsed
      uniforms.uniforms.uFormation = formation
      uniforms.uniforms.uSettled = settled
      uniforms.uniforms.uTheme = theme
      uniforms.uniforms.uMotionScale = motionScale
    })
  }

  const tick = (ticker: { deltaMS: number }) => {
    if (state.paused || destroyed) return
    const deltaSeconds = Math.min(ticker.deltaMS / 1000, 0.05)
    if (!state.reducedMotion && state.stage !== 'dormant') {
      elapsed += deltaSeconds * 0.6
    }
    if (!state.reducedMotion && state.stage !== 'dormant') {
      formationAge = Math.min(formationAge + deltaSeconds, 4.4)
      const settleProgress = Math.max(
        0,
        Math.min(1, (formationAge - 2.65) / 1.35),
      )
      settled = settleProgress * settleProgress * (3 - 2 * settleProgress)
    }
    const formationTarget = state.stage === 'dormant' ? 0 : 1
    const formationSpeed = state.stage === 'dormant' ? 4.2 : 0.42
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
    if (nextState.stage === 'dormant') {
      formationAge = 0
      settled = 0
    }
    if (enteringReady && nextState.reducedMotion) {
      formation = 1
      formationAge = 4.4
      settled = 1
    }
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
