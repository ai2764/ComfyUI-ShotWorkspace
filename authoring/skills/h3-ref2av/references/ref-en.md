# MiniMax H3 Ref2AV prompt contract

Use this guide only for Reference-to-Audiovisual generation. It defines one six-section prompt for one generated clip conditioned by supplied Pictures and optional Audios.

## Inputs and bindings

Pictures are numbered by actual connection order, starting at 1 with no gaps. Each Picture conditions the entire clip. Its tag identifies a visual source and never assigns that source to a moment on the timeline.

Before writing, create a compact manifest:

| Tag | Observed evidence | Single responsibility |
| --- | --- | --- |
| `<Picture 1>` | visible person, face, hair, clothing | character identity and wardrobe |
| `<Picture 2>` | visible vehicle, materials, silhouette | vehicle design |
| `<Picture 3>` | visible interior and control layout | environment geography |

Base observations on pixels and approved metadata. Filenames and labels are lookup aids, not visual evidence. If sources disagree about identity, wardrobe, object count, geography, or composition, resolve the conflict or split the generation. Do not hide conflicts by assigning sources different times.

Audios are independently numbered by connection order. Bind every submitted `<Audio N>` to one responsibility such as speaker identity, delivery, ambience, effects, beat, or audience-only music. Do not copy words from a voice reference unless the user supplies those words as target dialogue.

## Required JSON shape

Return JSON only, with no Markdown fence or surrounding explanation:

```json
{
  "subject_definitions": "...",
  "summary": "...",
  "retention_analysis": "...",
  "detailed_description": "...",
  "overall_soundscape": "...",
  "non_diegetic_music": "..."
}
```

Every value must be a non-empty string. Use the displayed key order.

### `subject_definitions`

Define every visible subject, location, vehicle, costume, and important prop. Cite the exact Picture tags that establish each property. Give every supplied Picture a concrete job.

### `summary`

Describe the complete clip in one short paragraph: dramatic action, visual direction, and main conditioning relationships. Do not introduce new tags or repeat dialogue.

### `retention_analysis`

Explain what remains stable from every Picture: identity, wardrobe, materials, silhouette, prop count, environment geometry, composition, or lighting. State any managed tension between references. Treat all references as whole-clip conditioning.

### `detailed_description`

Describe playback order with explicit ranges such as `0–2 seconds`. Every interval must stay within the requested duration. Include framing, camera behavior, subject positions, screen direction, eyelines, scale, environment, lighting, handled props, actions, reactions, and synchronized physical sounds.

At the first visible occurrence of a referenced element, cite its `<Picture N>` tag naturally and describe the preserved properties. The tag remains whole-clip conditioning even when action prose states when an element becomes visible.

Give every audible performer a stable ID such as `(S1)`. Preserve authored words and source language:

```text
Mia (S1) looks toward the controls and whispers, <d>[Chinese] 我们到了吗？</d>
```

Keep speaker, delivery, and action outside the `<d>` block. Put only `[Language]` and spoken words inside it. Do not repeat spoken words elsewhere.

### `overall_soundscape`

Summarize ambience and physical sounds. Do not repeat dialogue. Use `N/A` only when the user requests complete silence.

### `non_diegetic_music`

Describe only audience-only music. Specify instrumentation, tempo, rhythm, and dynamic development. Use the string `None` when absent in this application profile.

## Final validation

- Exactly six required JSON keys, all non-empty.
- Every submitted Picture and Audio tag appears with one stated responsibility.
- No unattached Picture or Audio tag appears.
- Picture order is never described as timeline order.
- All action intervals fit the requested duration.
- Dialogue appears exactly once, unchanged, inside valid `<d>` blocks.
- The clip is feasible and does not depend on incompatible reference states.
- A submitted ComfyUI graph uses `MiniMaxH3ReferenceToVideo` and connects every loaded image through `ref_images.ref_image_0...N`.
