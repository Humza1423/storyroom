# Model choices: baseline first, evidence before replacement

We have not proven that Gemini is the best model for this application. It is a practical initial cloud adapter for video observation and structured story proposals. No paid inference benchmark has been run without a user-provided key and rights-cleared real footage.

## Separate the jobs

| Candidate | Appropriate role | Current decision |
|---|---|---|
| Gemini Flash | Short-video observation and brief-driven structured proposals | Initial implementation; live quality unverified |
| SigLIP 2 | Text-to-frame retrieval without going through a caption | Strong next retrieval benchmark; static frames do not establish temporal actions |
| DINOv3 | Visual features for similarity / duplicate-shot candidates | Defer until repetitive footage is a measured issue |
| SAM 3.1 | Object segmentation and tracking | Defer; masks do not solve our story-assembly job |
| YOLO26 | Object and pose detections | Defer until explicit tags or movement features improve a measured task |
| InternVideo3 | Temporal video representation/understanding | Benchmark if action sequence errors dominate |
| Florence-2 | Frame descriptions, detection, and grounding | Possible image-level observation alternative |
| PySceneDetect | Visual cut/boundary detection | Useful for edited sources; continuous training actions can occur without cuts |

Sources: [SigLIP 2](https://huggingface.co/google/siglip2-base-patch16-224), [DINOv3](https://github.com/facebookresearch/dinov3), [SAM 3](https://github.com/facebookresearch/sam3), [YOLO26](https://docs.ultralytics.com/models/yolo26), [InternVideo3](https://github.com/OpenGVLab/InternVideo/tree/main/InternVideo3), [Florence-2](https://huggingface.co/microsoft/Florence-2-base), [PySceneDetect](https://www.scenedetect.com/docs/latest/api/detectors.html).

The screenshot's stars are not app-specific evidence. A model that excels at masks may be irrelevant to choosing a compelling source range. The model, checkpoint, resolution, sampling rate, hardware, and dataset all matter.

## What we should compare

Hold the interface and evaluation footage fixed. Compare description search against SigLIP frame retrieval and, if justified, video embeddings. Use 20 or more human-reviewed queries spanning visible objects, framing, activities, temporal actions, and unsupported requests.

Measure useful candidates in the first five, missed relevant moments, boundary usefulness, indexing time, search latency, peak memory, cost per source minute, and installation complexity. Use the same held-out shoots for every candidate. Do not add all seven models and attribute any improvement to “the AI stack.”

The first comparison should focus on direct visual search versus description search. A hybrid may be useful, but it must improve results enough to pay for its additional processing and maintenance.

## Using a model versus training it

Inference uses existing learned weights. Embedding/indexing stores representations of your clips; that is not training. Fine-tuning changes model weights using labeled examples. Our planned custom ranker learns which candidates fit a requested section. It does not learn to see video from scratch.

More raw videos do not automatically provide training labels. A good dataset needs a task, examples, expected answers, source rights, and a held-out split that keeps related footage together. AI-generated descriptions are not ground truth for evaluating the same AI.

## What your hardware changes

Your 8 GB Apple Silicon machine is adequate for this bounded local application and small ML experiments. It does not mean every video model in the table can run conveniently alongside the application. Official SAM 3 installation, for example, specifies a CUDA GPU; that is not your Mac's hardware. Prefer small, separately benchmarked inference experiments before downloading large checkpoints.

We will not purchase GPUs, switch providers, or download a collection of large models to create the appearance of technical depth. The serious engineering is making useful results repeatable, bounded in cost, recoverable, and correctly connected to the editing workflow.
