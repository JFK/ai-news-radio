/** Gemini TTS model and voice options (shared between Settings and EpisodeDetail). */

export const GEMINI_TTS_MODELS = [
  { value: "gemini-2.5-flash-preview-tts", label: "Flash (Fast/Low cost)" },
  { value: "gemini-2.5-pro-preview-tts", label: "Pro (High quality)" },
];

export const GEMINI_TTS_VOICES = [
  { value: "Kore", label: "Kore - 落ち着いた女性声、ニュース向き" },
  { value: "Puck", label: "Puck - 明るい男性声、カジュアル" },
  { value: "Charon", label: "Charon - 知的な男性声、解説向き" },
  { value: "Fenrir", label: "Fenrir - 元気な男性声、エンタメ向き" },
  { value: "Aoede", label: "Aoede - 自然な女性声、語り向き" },
  { value: "Leda", label: "Leda - 若々しい女性声、ポップ" },
  { value: "Orus", label: "Orus - 力強い男性声、フォーマル" },
  { value: "Zephyr", label: "Zephyr - 明るい女性声、親しみやすい" },
  { value: "Achernar", label: "Achernar - 柔らかい女性声、穏やか" },
  { value: "Gacrux", label: "Gacrux - 落ち着いた女性声、ドキュメンタリー向き" },
  { value: "Sulafat", label: "Sulafat - 温かい女性声、案内向き" },
];

/** Helper: extract value arrays for Settings select fields. */
export const GEMINI_TTS_MODEL_VALUES = GEMINI_TTS_MODELS.map((m) => m.value);

/** Helper: build { value: label } maps for Settings optionLabels. */
export const GEMINI_TTS_MODEL_LABELS = Object.fromEntries(
  GEMINI_TTS_MODELS.map((m) => [m.value, m.label]),
);
