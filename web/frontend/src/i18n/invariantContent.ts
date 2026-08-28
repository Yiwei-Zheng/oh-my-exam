export const BRAND_NAME = 'OH-MY-EXAM'
export const HERO_PREFIX = "OH, I'M"

export const HERO_PHRASES = [
  'ANSWERING FASTER',
  'GETTING HIGHER SCORES',
  'LEARNING DEEPER',
  'THINKING CLEARER',
] as const

export const ACADEMIC_ORBIT_SEGMENTS = [
  [
    '∫₀^∞ e^(−x²) dx = √π/2',
    'F = ma',
    '2H₂O ⇌ H₃O⁺ + OH⁻',
    'MC = dC/dQ',
    'O(log n)',
  ],
  [
    'e^(iπ) + 1 = 0',
    'E₀ = mc²',
    'pH = −log₁₀ a(H⁺)',
    'Q_d = a − bP',
    'def square(x): return x ** 2',
  ],
  [
    '∇ · E = ρ/ε₀',
    'ΔG = ΔH − TΔS',
    'MR = d(TR)/dQ',
    'const pass: boolean = score >= 60',
    'P(A ∩ B) = P(A)P(B|A)',
  ],
  [
    'P(A|B) = P(B|A)P(A)/P(B)',
    'PV = nRT',
    'ΔS_total ≥ 0',
    'SELECT subject, AVG(score) FROM exams GROUP BY subject;',
    'λ = h/p',
  ],
  [
    'a² + b² = c²',
    '2H₂ + O₂ → 2H₂O',
    'price elasticity = %ΔQ_d / %ΔP',
    'T(n) = O(n log n)',
    'interface Exam { score: number }',
  ],
] as const
