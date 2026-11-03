# Workflow Interface

Inspect the receiving workflow's inputs first. Keep Shot Workspace and Workflow Interface outside its original groups, leaving the author's layout recognizable.

| Our output | Receiving input |
| --- | --- |
| prompt (STRING) | Native encoder prompt |
| image_1 … image_9 (IMAGE) | Picture sockets in order; native H3 starts at ref_image_0 |
| width / height / frame_count | Connect only when canvas/timing semantics agree |
| fps | Compatible source/assembly rate; this authoring contract uses 24 fps |

Only intercept the required entry wires. MultiRef keeps its own masks, context length and controller; one shot does not take over every extension stage.

## Media boundary

Shot Standard Media Outputs passes explicit AUDIO, VIDEO, frames/audio and native LATENT unchanged. It does not choose a previous take, convert latent formats, or automatically bind video/audio in the writer.

```text
Original sampler → original compatible video/audio decoders
  → Create Video → VIDEO → receiving Get Video Components
  → receiving context frames + context audio
```

Reuse existing output chains; many workflows already decode or output VIDEO. A saver returning paths needs a real file loader or VIDEO assembly. Filenames and incompatible latent dictionaries cannot be cast to VIDEO.

Native LATENT handoff requires agreement on the complete structure and timing. H3 AV caches can contain nested video/audio streams; the socket label alone is insufficient.

## Timing and generation

One queue captures the active shot only. Samplers and savers stay external. Generate requires a current accepted prompt and dependent output branch; a disconnected node reports the missing branch.

Sampling duration precedes overlap trimming. Account for the protected prefix and final trim when targeting delivered duration. The result panel reads file duration, without promising exact output cropping.

## LLM connection

Text/vision roles use OpenAI-compatible chat completions. Context capacity is configured on the model server. Each request supplies application authoring rules, reference descriptions and shot data; this node does not set server context capacity.

Unload before generation is opt-in, off by default, and needs a provider-specific URL sharing the LLM origin. If enabled and unloading fails, generation submission stops.
