# Prompt Context Leakage Audit

Generated: 2026-06-14T17:02:12.530648

## Summary

| Context Mode | Status | Unsafe Fields | Title Matches | Prefix Matches | Any Leakage |
|---|---|---|---:|---:|---:|
| legacy | **FAIL** | synthesis_narrative, predecessor.role, predecessor.relationship_sentence | 5/77 | 23/77 | 28/77 |
| clean | **PASS** | none | 0/77 | 0/77 | 0/77 |

## Legacy Context

- Description: Predecessor title + role + relationship_sentence + synthesis_narrative
- Status: **FAIL**
- Total targets: 77
- Exact title matches: 5
- Exact contribution matches: 0
- Exact abstract matches: 0
- Title prefix matches: 23
- Any leakage: 28

### Flagged Examples

**0biUwyjKkm**: OpenHOI: Open-World Hand-Object Interaction Synthesis with Multimodal Large Lang...

- Title prefix: `OpenHOI`
- Leakage: {'exact_title_match': False, 'exact_contribution_match': False, 'exact_abstract_match': False, 'title_prefix_match': True, 'any_leakage': True}
- Context preview:
```
## Predecessor Papers

1. **Do As I Can, Not As I Say: Grounding Language in Robotic Affordances (SayCan)**
   - Role: Conceptual foundation for language-to-affordance grounding and task decomposition...
```

**4xvE6Iy77Y**: PRIMT: Preference-based Reinforcement Learning with Multimodal Feedback and Traj...

- Title prefix: `PRIMT`
- Leakage: {'exact_title_match': False, 'exact_contribution_match': False, 'exact_abstract_match': False, 'title_prefix_match': True, 'any_leakage': True}
- Context preview:
```
## Predecessor Papers

1. **Deep Reinforcement Learning from Human Preferences**
   - Role: Foundational preference-based RL and reward modeling from pairwise trajectory comparisons
   - Relationship:...
```

**8P3QNSckMp**: A Clean Slate for Offline Reinforcement Learning...

- Title prefix: ``
- Leakage: {'exact_title_match': True, 'exact_contribution_match': False, 'exact_abstract_match': False, 'title_prefix_match': False, 'any_leakage': True}
- Context preview:
```
## Predecessor Papers

1. **D4RL: Datasets for Deep Data-Driven Reinforcement Learning**
   - Role: benchmark/dataset
   - Relationship: The paper’s evaluation protocol is built to rectify shortcoming...
```

**B6bE2GC71a**: EvoLM: In Search of Lost Language Model Training Dynamics...

- Title prefix: `EvoLM`
- Leakage: {'exact_title_match': False, 'exact_contribution_match': False, 'exact_abstract_match': False, 'title_prefix_match': True, 'any_leakage': True}
- Context preview:
```
## Predecessor Papers

1. **Pythia: A Suite for Analyzing Large Language Models Across Training and Scaling**
   - Role: Methodological blueprint for transparent training-dynamics analysis
   - Relati...
```

**Gq4Gay8rDB**: PlayerOne: Egocentric World Simulator...

- Title prefix: `PlayerOne`
- Leakage: {'exact_title_match': False, 'exact_contribution_match': False, 'exact_abstract_match': False, 'title_prefix_match': True, 'any_leakage': True}
- Context preview:
```
## Predecessor Papers

1. **NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis**
   - Role: Neural scene representation and view synthesis backbone
   - Relationship: PlayerOne’s j...
```

## Clean Context

- Description: Predecessor titles only
- Status: **PASS**
- Total targets: 77
- Exact title matches: 0
- Exact contribution matches: 0
- Exact abstract matches: 0
- Title prefix matches: 0
- Any leakage: 0

