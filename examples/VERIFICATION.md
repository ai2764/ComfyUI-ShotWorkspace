# Verification scope

## Completed local source runs

| Source integration | Recorded outcome |
| --- | --- |
| Original Motion Context, native AV latent route | Completed generation: 704×480, 24 fps, 51 delivered frames after 22-frame context trim from 73 input frames |
| Original Motion Context, decoded video route | Completed generation with explicit previous VIDEO and matching frames/audio; same 51-frame delivered shape |
| MultiRef AV Extension | Completed one extension, protected 39-frame context, four sampler steps and existing decoder; standard VIDEO saver produced 704×480 at 24 fps, approximately 5.167 seconds |

Source outputs passed full audio/video decoding. MultiRef kept the original 102-node/20-group canvas plus six interface nodes. Its source was a selected previous clip, not automatic feedback. Private character media and production receipts are not distributed.

## Redistributed variants

Public files derive from those connected graphs. Node positions/sizes, group bounds and graph links are preserved. Private descriptions, provider configuration, job state and filenames were removed or replaced. A separate bootstrap helper starts at slot zero and bypasses the empty media adapter; the continuation template explicitly loads slot one and saves slot two.

Public fixture images, video and silence are deterministic connection-testing inputs, not the private source renders' inputs. The public variants were subsequently GPU-rendered successfully. All four delivered files passed full audio/video decoding; their hashes, dimensions, durations and execution status are in `results/VERIFICATION.json`. These small color-block outputs verify the integration, not cinematic quality or arbitrary model compatibility.

The separate full Motion Context v0.7 original-layout connection reference is canvas/entry-wire checked, but complete original-v0.7 inference is not certified. Resolve its additional dependencies in your installation.

## Pinned originals

- NikoDemon80/ComfyUI-H3-Motion-Context: `518c083d11d80fa5920222ad89889924ee4401c9`, `example_workflows/H3-Motion-Context-v0.7.json`; SHA-256 `0c33daa8da99001f6b716f251667ad01e4b3471351081426f7535478d3ee2800`.
- seitanism/ComfyUI-H3-Motion-Context-MultiRef: `361624fb406b63eb6694442eac6c895fc1533a70`, `example_workflows/NEW - AV Extension.json`; SHA-256 `87a85563ab868d4202a3f37f02e30d4749b865bcf8b050f55991a6c980ca9fa4`.
- Compact Motion Context examples derive from Comfy-Org's H3 template plus an external native adapter, not the full v0.7 graph. The original official JSON and metadata are included in `tests/fixtures/upstream/official`.


## Public fixture reruns

| Output | Size | FPS | Duration |
| --- | --- | --- |
| [motion-context-video.mp4](results/motion-context-video.mp4) | 704×480 | 24/1 | 2.125s |
| [native-latent-first.mp4](results/native-latent-first.mp4) | 704×480 | 24/1 | 3.042s |
| [native-latent-continuation.mp4](results/native-latent-continuation.mp4) | 704×480 | 24/1 | 2.125s |
| [multiref-latent-context.mp4](results/multiref-latent-context.mp4) | 704×480 | 24/1 | 5.167s |

The first native-latent attempt through an empty media output completed with no video. The distributed bootstrap helper bypasses that empty adapter; its first clip and the subsequent continuation both rendered successfully. No production services were restarted.

## Test environment

`results/ENVIRONMENT.json` records backend and dependency revisions. The working ComfyUI core and H3-Optimizations installation contained local tracked changes, so commit hashes alone do not reproduce the entire model runtime. Those core/optimization patches and model weights are not part of this node package. Use a compatible H3 model-loading environment and quantization; these runs are not a certification of every unmodified upstream installation.
