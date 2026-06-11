# Sample Baseline Prompt

Target: OpenHOI: Open-World Hand-Object Interaction Synthesis with Multimodal Large Language Model

---

You are an expert AI researcher. Given the following set of predecessor papers that influenced a research direction, generate 10 distinct research ideas that could advance this direction.

## Predecessor Papers

1. **Do As I Can, Not As I Say: Grounding Language in Robotic Affordances (SayCan)**
   - Role: Conceptual foundation for language-to-affordance grounding and task decomposition
   - Relationship: OpenHOI’s MLLM jointly grounds affordances and decomposes free-form instructions into sub-tasks, directly echoing SayCan’s principle of coupling LLM semantics with environment/affordance signals for executable long-horizon plans.
2. **LLaVA: Large Language and Vision Assistant**
   - Role: Methodological precedent for multimodal LLMs via visual instruction tuning
   - Relationship: OpenHOI builds on the LLaVA-style visual instruction tuning recipe to align language with visual inputs, adapting the paradigm to 3D inputs for open-vocabulary HOI guidance and instruction following.
3. **3D-LLM: Injecting the 3D World into Large Language Models**
   - Role: Model component precedent for 3D-aware multimodal LLMs
   - Relationship: The paper’s 3D MLLM for affordance grounding/localization is a natural extension of 3D-LLM’s approach to infusing 3D scene representations into LLMs, enabling object-part reasoning (e.g., handles, buttons) in 3D.
4. **Where2Act: From Pixels to Actions for Articulated Object Manipulation**
   - Role: Algorithmic foundation for actionable region/affordance localization on objects
   - Relationship: OpenHOI’s precise localization of interaction regions inherits the idea of predicting actionable object parts from Where2Act, extending it to open-vocabulary language grounding and long-horizon HOI sequences.
5. **Human Motion Diffusion Model (MDM)**
   - Role: Methodological precedent for diffusion-based motion synthesis
   - Relationship: OpenHOI’s affordance-driven diffusion generator for hand-object interactions is built on the MDM paradigm, using diffusion to synthesize temporally coherent, conditioned motion sequences.
6. **PhysDiff: Physics-Guided Human Motion Diffusion**
   - Role: Algorithmic precedent for physics guidance/refinement in motion generation
   - Relationship: OpenHOI’s training-free physics refinement echoes PhysDiff’s strategy of injecting physics constraints into diffusion sampling to enforce contact and feasibility, adapted here to hand–object contact and manipulation.
7. **ArtiGrasp: Learning to Interact with Articulated Objects in 3D**
   - Role: Methodological precedent for articulation-aware hand–object interaction synthesis
   - Relationship: OpenHOI’s focus on object-part affordances (handles/buttons) and physically plausible hand interactions draws directly from ArtiGrasp’s articulation- and contact-aware modeling of 3D hand–object manipulation.

## Synthesis Narrative

OpenHOI’s core contribution—open-world HOI synthesis that follows free-form language while generalizing to novel objects—emerges from the convergence of three research lines. First, SayCan established that LLMs become actionable planners when grounded in affordances and cost-to-go estimates, which OpenHOI adapts to hand–object manipulation by jointly learning semantic task decomposition and affordance grounding in a single 3D MLLM. Second, visual-instruction-tuned MLLMs (LLaVA) and their 3D counterparts (3D-LLM) provide the training recipe and representational interface to align language with geometric context; OpenHOI extends this to localize interaction-relevant parts (e.g., handles, buttons) and to parse complex, long-horizon commands into executable sub-tasks in 3D. Third, for physically plausible synthesis, diffusion-based motion generation (MDM) gives the backbone for producing long, coherent interaction trajectories. This is complemented by physics-aware guidance exemplified by PhysDiff, inspiring OpenHOI’s training-free refinement to enforce contact and feasibility without extra learning. Finally, HOI- and articulation-focused work such as Where2Act and ArtiGrasp directly inform OpenHOI’s affordance-driven conditioning: predicting actionable regions on articulated objects and modeling contact/part interactions. Together, these works concretely enable OpenHOI’s key innovation: an affordance-conditioned diffusion pipeline steered by a 3D MLLM that both grounds open-vocabulary semantics in object parts and decomposes tasks, yielding long-horizon, physically consistent hand–object interactions for unseen objects.

## Task

Generate exactly 10 research ideas that could be the next step in this research direction. Each idea should:

1. Build directly on the predecessors listed above.
2. Be specific enough that another researcher could evaluate whether it is worth pursuing.
3. Address a clear gap, limitation, or opportunity identified in the predecessors.

## Output Format

Return a JSON array of exactly 10 objects, each with:
- "idea_title": A concise title for the research idea (10-15 words)
- "idea_description": A 2-3 sentence description of the idea
- "key_innovation": What is novel about this idea compared to the predecessors
- "addressed_gap": Which gap or limitation from the predecessors this addresses

Return ONLY the JSON array, no other text.
