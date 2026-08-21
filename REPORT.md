# ConvFinQA Report

To iterate on new possible techniques, I started with a small set of approaches and scorers and slowly evolved them to 

## Method

### Approaches

To compare results, I implemented 4 approaches

- Baseline: An “answer-only” approach similar to the paper’s baseline, where the model answers directly without using external tools.
- Calculator tool: The model extracts the relevant values and uses a deterministic calculator tool to perform the arithmetic.
- Program of thought: The model generates and executes a short program to calculate the answer, reducing reliance on mental arithmetic.
- Evidence first: The model first retrieves relevant facts from the document, then performs calculations using only those grounded values.

For each run below, I took random sample of 30 mainly due to cost and reused the same id's to see and compare the outcome across these approaches

### Prompt content

Below is the general shape for what goes into the prompt as context

```
[Approach-specific instructions]
{...}

<conversation_history>
{previous questions and model responses; omitted on the first turn}
</conversation_history>

<document_context>
{the financial report’s pre-text, table data, and post-text}
</document_context>

<user_question>
{the current ConvFinQA question}
</user_question>
```

### Scorers

The evaluation used the following scorers:

- Turn execution accuracy: Measures whether each answer matches the expected executed result, accounting for numeric units, percentages, and formatting differences.
- Conversation exact accuracy: Scores a conversation as correct only when every turn is answered correctly.
- Parse failure rate: Measures how often a response does not contain a usable final answer.
- Numerical accuracy: Compares the predicted and expected numeric values using a tolerance to account for minor rounding differences.
- Contains accuracy: Checks whether the expected answer appears in the response. This is retained as a simple legacy formatting diagnostic.

## Error Analysis

Below is the original paper's results, this acts as a good baseline for us to review the techniques applied below

```
approach                           execution accuracy
GPT-3 Answer-only                  24.09% ± 0.61
GPT-3 Program-original             40.81% ± 4.68
GPT-3 Program-normal               45.15% ± 2.77
GPT-3 CoT prompting                40.63% ± 1.25
FinQANet RoBERTa-large             68.90%
FinQANet-Gold RoBERTa-large        77.32%
General crowd                      46.90%
Human experts                      89.44%
```

### Round 1

#### Approaches

The original run compared three v1 approaches on the same 30-record cohort: `evidence:v1` was added in later rounds as part of improvement)

- `baseline:v1`: direct answer generation without tools.
- `baseline-tool:v1`: answer generation with the calculator tool required.
- `program-of-thought:v1`: answer generation with code execution required.

#### Score outcome

The last three metrics were applied retrospectively to the original outputs.

```
baseline:v1                                                                               

scorer                          mean    stderr
numeric_accuracy                0.601   0.055
contains_accuracy               0.363   0.061
turn_execution_accuracy         0.333   0.045
conversation_exact_accuracy     0.000   0.000
parse_failure_rate              0.007   0.007

baseline-tool:v1

scorer                          mean    stderr
numeric_accuracy                0.615   0.057
contains_accuracy               0.435   0.070
turn_execution_accuracy         0.365   0.048
conversation_exact_accuracy     0.033   0.033
parse_failure_rate              0.000   0.000

program-of-thought:v1

scorer                          mean    stderr
numeric_accuracy                0.670   0.055
contains_accuracy               0.473   0.065
turn_execution_accuracy         0.398   0.054
conversation_exact_accuracy     0.067   0.046
parse_failure_rate              0.000   0.000   
```

- [Open in local Inspect viewer]([http://127.0.0.1:7575/#/tasks/2026-08-20T02-47-11-00-](http://127.0.0.1:7575/#/tasks/2026-08-20T02-47-11-00-)    

     00_convfinqa_Xe9ckj7bD2HBG7X3Ct9aGP.eval/samples)
- [Saved evaluation archive](server/core/evals/.report/2026-08-20T02-47-11-00-

     00_convfinqa_Xe9ckj7bD2HBG7X3Ct9aGP.eval)

 The low scores came from a combination of scorer limitations, dataset defects, and genuine reasoning errors.

#### Failure modes

##### Scorer limitations

- `Double_HII/2017/page_104.pdf`: expected `-4`; the response said “decreased by $4 million,” but the scorer extracted positive `4`.
- `Single_UNP/2011/page_76.pdf-1`: expected `2200 million`; the response gave the equivalent `$2.2 billion`, but the scorer selected a year instead.

These examples showed that the original scorer did not reliably normalize signs, percentages, units, or multiple numeric candidates.

##### Dataset defects

- `Double_AMAT/2013/page_18.pdf`: the question asks for a 2013-to-2014 change, but the document and reference calculation use 2012 and 2013.
- `Single_IPG/2008/page_62.pdf-1`: questions reference 2007 liabilities, while some annotated answers come from the 2008 column.

These records were excluded from the genuine-failure category because their reference data was internally inconsistent. The remaining incorrect results were treated as genuine model failures only after accounting for scorer and annotation problems.

### Round 2

#### Changes from round 1

- Added v2 for all prompts to be more precise with units and format
- Updated the scorer to handle more variations (1 kg + 1000 gram is equivalent)

#### Approaches

Round 2 evaluated the three v2 approaches on the same 30-record cohort:

- `baseline:v2`: direct generation without tools.
- `baseline-tool:v2`: generation with the calculator required.
- `program-of-thought:v2`: generation with code execution required.



```
baseline:v2
scorer                          mean    stderr
numeric_accuracy                0.764   0.055
contains_accuracy               0.626   0.047
turn_execution_accuracy         0.754   0.055
conversation_exact_accuracy     0.500   0.093
parse_failure_rate              0.021   0.017

baseline-tool:v2
scorer                          mean    stderr
numeric_accuracy                0.631   0.054
contains_accuracy               0.586   0.048
turn_execution_accuracy         0.631   0.054
conversation_exact_accuracy     0.233   0.079
parse_failure_rate              0.039   0.023

program-of-thought:v2
scorer                          mean    stderr
numeric_accuracy                0.745   0.061
contains_accuracy               0.620   0.050
turn_execution_accuracy         0.745   0.061
conversation_exact_accuracy     0.567   0.092
parse_failure_rate              0.035   0.020
```

- [Open in local Inspect viewer]([http://127.0.0.1:7575/#/tasks/2026-08-20T06-37-30-00-](http://127.0.0.1:7575/#/tasks/2026-08-20T06-37-30-00-)    

     00_convfinqa_TEv4gFoA9YaXYQUKTNfchJ.eval/samples)
- [Saved evaluation archive](server/core/evals/.report/2026-08-20T06-37-30-00-

     00_convfinqa_TEv4gFoA9YaXYQUKTNfchJ.eval)

### Round 3

#### Changes from Round 2

Round 3 introduced stricter, auditable execution:

- Replaced free-text `Final answer:` responses with structured outputs.
- Added `evidence:v1`, which retrieves indexed evidence before using a grounded calculator.
- Replaced the hosted Code Interpreter in `program-of-thought:v2` with an evidence-selection stage and an audited Decimal arithmetic program.
- Treated malformed JSON, invalid evidence references, unsupported operations, and incorrect calculator references as failures without falling back to prose.

#### Score outcome

```
baseline:v3
scorer                          mean    stderr
numeric_accuracy                0.562   0.063
contains_accuracy               0.571   0.054
turn_execution_accuracy         0.562   0.063
conversation_exact_accuracy     0.200   0.074
parse_failure_rate              0.000   0.000

evidence:v1
scorer                          mean    stderr
numeric_accuracy                0.448   0.064
contains_accuracy               0.447   0.057
turn_execution_accuracy         0.448   0.064
conversation_exact_accuracy     0.100   0.056
parse_failure_rate              0.301   0.033

program-of-thought:v3
scorer                          mean    stderr
numeric_accuracy                0.400   0.057
contains_accuracy               0.011   0.011
turn_execution_accuracy         0.400   0.057
conversation_exact_accuracy     0.067   0.046
parse_failure_rate              0.045   0.021
```

#### Sources

There's 2 sources because the evidence run failed and had to be re-ran

Baseline and program-of-thought

- Open in local Inspect viewer ([http://127.0.0.1:7575/#/tasks/2026-08-20T22-21-17-00-00_convfinqa_4FqDuxeEVRXUz6Vr334dyb.eval/samples](http://127.0.0.1:7575/#/tasks/2026-08-20T22-21-17-00-00_convfinqa_4FqDuxeEVRXUz6Vr334dyb.eval/samples))
- Saved evaluation archive (server/core/evals/.report/2026-08-20T22-21-17-00-00_convfinqa_4FqDuxeEVRXUz6Vr334dyb.eval)

Corrected evidence run

- Open in local Inspect viewer ([http://127.0.0.1:7575/#/tasks/2026-08-20T23-37-40-00-00_convfinqa_6hM38FXyC8pMJ5E289GzTW.eval/samples](http://127.0.0.1:7575/#/tasks/2026-08-20T23-37-40-00-00_convfinqa_6hM38FXyC8pMJ5E289GzTW.eval/samples))
- Saved evaluation archive (server/core/evals/.report/2026-08-20T23-37-40-00-00_convfinqa_6hM38FXyC8pMJ5E289GzTW.eval)



## Findings

- Round 3 performed worse than Round 2 because strict structured outputs introduced additional validation and orchestration failures, including a 0.301 parse-failure rate for evidence:v1.
- baseline:v2 achieved the highest turn accuracy, suggesting that precise prompt design was more effective than adding calculator or evidence stages.
- program-of-thought:v2 achieved the highest conversation exact accuracy, so the baseline was not strongest on every metric.

## Future Work

### Specific  financial knowledge in the context

Genuine failure points indicate lack of technical financial knowledge, a few techniques below could bolster those results

- We can fine-tune a LORA on trained on financial textbooks and synthetic data, this can exposed as a tool call to gather financial context to a SOTA reasoning model
- We can also fetch related financial terms, inject into context
- We can continuously train an existing model to inject more financial knowledge

### Allow the hallucination error catch

Another technique to catch hallucination is to adopt an ensemble approach, we can either have 3 parallel attempts with different temperature and observe if they all reach the same outcome. If they do then there's a high confidence that the result is derived correctly and if they don't then we can 

### Improve

One technique that might be interesting is to use GraphRag on entity and relationship that tries to capture the technical details between techinical details. Something like

```
ACME -> purchase amount -> $1000 -> in year of -> 2007
    |
    |-> sold amount -> $2000 -> in year of -> 2007
```

And inject that to context to observe if the models perform better. 

## Strength and weakness of evaluations and approaches

#### Strength

- Multiple approach assessment allows a general stab at the problem and let's us compare between them.
- Versioning of prompts and approach to be able to compare and perform ablation to see what made a difference
- Scorers tried to be comprehensive across different attributes to review.

#### Weakness

- Baseline scored quite high compared to original GPT-3, suggest model is already exposed to these documents and so these techniques might not show too much.
- No recovery for having a wrong answer for an earlier turn which leads overall all subsequent turns being wrong
- We re-ran the same 30 samples to be able to compare and each improvements was based of the failure modes of these errors.

## If &amp; how you've used coding assistants or gen AI tools to help with this assignment

- Gall's principle: I hand wrote the initial patterns I wanted and then asked AI to infer.
- Heavy pattern enforcement: When it doesn't follow pattern I steer it, if it still fails I override by manually writing
- Each code path is reviewed and deleted if it doesn't fit well.

## Other

The above are report for the agentic performance, below is a general statement on the software (frontend/backend/infra) choices

### Software

#### Strength

- Observability for traces / logs / metrics are built in using OpenTelemetry
- Very strong patterns enforcement for service/repo/schema/router
- Strong type consistency with pydantic / OpenAPI contract / zod with tanstack ecosystem
- Adopt ag-ui pattern which allows standard protocol for event emission (with tool calling)

#### Weakness

- Doesn't have durable execution for agentic runs . Not as needed right now since all approaches are short in nature, but will be useful if techniques requires some long running task
- There's no pre-processing step for other techniques, if we have something that needs it I would re-use the durable execution above to allow background work to be quite tracable


