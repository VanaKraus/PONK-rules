# Start

Install the dependencies from `requirements.txt` and start the server with `uvicorn server:app` (or `uvicorn server:app --reload`). 

Tested on Python 3.14.

# Run

Send a multipart POST request to `/raw`. Parameters include:

- `file`: .conllu file (as a form file)
- `profile`: requested [profile](#rules-metrics-and-profiles) (an URL parameter; optional, defaults to "default")

Also see `:8000/docs`.

Happy rule-based simplification :^)

## Response structure

See below for an [example response](#example-response), [rule annotation behavior](#rule-annotations) as well as for the descriptions of the [metrics and rules](#rules-metrics-and-profiles).

- `modified_conllu` (str): the .conllu content annotated (and potentially amended) by the rules
- `metrics` (list): metrics about the provided .conllu file
- `metric_info` (dict): explanatory info about the metrics that were measured
  - `<METRIC>` (dict):
    - `cz_name`/`en_name` (str): a human-readable name of the metric
    - `cz_doc`/`en_doc` (str): a human-readable description of the metric
    - `cz_hint`/`en_hint` (str, optional): human-readable advice on how to improve the input text with respect to the metric
    - `intervals` (dict, optional): bins describing informatory assessments of values of the metric
      - `bad` (list): the input text is akin to less readable documents with respect to the metric; given as the lower bound and the upper bound, `null` means -infinity/+infinity
      - `medium` (list): the input text is akin to both more and less readable documents with respect to the metric; given as the lower bound and the upper bound, `null` means -infinity/+infinity
      - `good` (list): the input text is akin to both more readable documents with respect to the metric; given as the lower bound and the upper bound, `null` means -infinity/+infinity
    - `order` (int): order in which to display the metric
  - `rule_info` (dict): explanatory info about the rules that applied during this request
    - `<RULE>` (dict):
      - `cz_name`/`en_name` (str): a human-readable name of the rule
      - `cz_doc`/`en_doc` (str): a human-readable description of the rule
      - `cz_participants`/`en_participants` (dict): human-readable descriptions of annotations given by the rule
      - `foreground_color` (dict | null): foreground color to highlight the annotated tokens with
      - `background_color` (dict | null): background color to highlight the annotated tokens with
      - `order` (int): order in which to display the rule
  - `conflict_background_color` (dict): background color for highlighting tokens with more than one annotation

## Example response

```json
{
  "modified_conllu": "# newdoc\n# newpar\n# sent_id = 1\n# text = Tohle je test.\n1\tTohle\ttenhle\tDET\tPDNS1----------\tCase=Nom|Gender=Neut|Number=Sing|PronType=Dem\t3\tnsubj\t_\tTokenRange=0:5\n2\tje\tbýt\tAUX\tVB-S---3P-AAI--\tAspect=Imp|Mood=Ind|Number=Sing|Person=3|Polarity=Pos|Tense=Pres|VerbForm=Fin|Voice=Act\t3\tcop\t_\tTokenRange=6:8\n3\ttest\ttest\tNOUN\tNNIS1-----A----\tAnimacy=Inan|Case=Nom|Gender=Masc|Number=Sing|Polarity=Pos\t0\troot\t_\tSpaceAfter=No|TokenRange=9:13\n4\t.\t.\tPUNCT\tZ:-------------\t_\t3\tpunct\t_\tSpaceAfter=No|TokenRange=13:14",
  "metrics": [
    {
      "sent_count": 1
    },
    {
      "word_count": 3
    }
  ],
  "rule_info": {
    "RuleDoubleAdpos": {
      "background_color": {
        "blue": 67,
        "green": 45,
        "red": 123
      },
      "cz_doc": "Dokumentace pravidla",
      "cz_name": "Pravidlo dvojité obměny",
      "cz_participants": {
        "adpos": "Adpozice s nejasnou valencí"
      },
      "en_doc": "Rule documentation",
      "en_name": "Double adposition rule",
      "en_participants": {
        "adpos": "Adposition with an unclear valence"
      },
      "order": 5
    }
  },
  "metric_info": {
    "smog": {
      "cz_doc": "Měří čitelnost text v letech vzdělání nutných k pochopení textu.",
      "cz_hint": "Používejte méně dlouhých slov a kratší věty/souvětí. Pište uvolněněji, méně technicky.",
      "cz_name": "SMOG index",
      "en_doc": "Measures readability in years of education necessary for successful understanding.",
      "en_hint": "Use fewer long words, and shorter sentences. Make your writing more relaxed and less technical.",
      "en_name": "SMOG index",
      "intervals": {
        "bad": [
          13.62265750478578,
          null
        ],
        "good": [
          null,
          12.320016079839352
        ],
        "medium": [
          12.320016079839352,
          13.62265750478578
        ]
      },
      "order": 17
    }
  },
  "conflict_background_color": {
    "red": 114,
    "green": 114,
    "blue": 114
  }
}
```

## Rule annotations

Rule annotations get added to the MISC column in the .conllu file. The general structure is:

```
PonkApp1:<rule_id>:<application_id>=<participant>
```

- `rule_id`: ID of the rule being annotated
- `application_id`: ID of the application of the rule; if two tokens have the same `application_id`, they were annotated by the same application of the given rule
- `participant`: a rule-specific description of how the token relates to the phenomenon controlled by the rule

### Correction suggestions

When allowed (see [below](#rules-metrics-and-profiles)), some rules can suggest corrections. A correction suggestion consists of one or more special annotations bound together by a shared `application_id`.

Special annotations can appear in the MISC column:

```
PonkApp1:<rule_id>:<application_id>:<action>=<info>
```

Special annotations can also appear in the sentence header:

```
# PonkApp1:<rule_id>:<application_id>:<action> = <info>
```

- `rule_id`: ID of the rule being annotated
- `application_id`: ID of the application of the rule
- `action`: what to do with the token (see below)
- `info`: an action-dependent description of the action

Note that the if the special annotations appear in the MISC column, they do so *beside* the regular rule annotations.

```
PonkApp1:RuleTooLongExpressions:fde7d51c=v_důsledku_toho|PonkApp1:RuleTooLongExpressions:fde7d51c:remove=_
```

Here, a token has been anotated by a rule with `application_id` of fde7d51c; during the same application, a correction is suggested.

```
PonkApp1:RuleTooLongExpressions:bee105bf:remove=post-process
```

Here, a token has not been annotated by any rule, but is part of a correction suggestion made by `application_id` of bee105bf nevertheless.

#### Remove 

The `remove` action states that the token should be completely removed from the conllu structure. It is annotated in the MISC column.

The `info` field is either `_` or `post-process` and can be ignored.

```
PonkApp1:RuleTooLongExpressions:fde7d51c:remove=_
PonkApp1:RuleTooLongExpressions:bee105bf:remove=post-process
```

#### Add

The `add` action states that a new token should be inserted into the dependency structure. The `<info>` field is a JSON dictionary with the following structure:

- `id`: an ID of the new token; it may get referred to by other actions within the rule application
- `add_after`: after which token the new token should be inserted
- `parent`: parent of the new token; for technical reasons, the value provided in `node` (below) is invalid
- `preserve_capitalization`: whether capitalization of the new node is required to remain unmodified
- `node`: a dict with the values of the CoNLL-U columns

```
# PonkApp1:RuleTooLongExpressions:324aa381:add = {"id": "new_c3bf3e84", "add_after": "3", "parent": "5", "preserve_capitalization": false, "node": {"form": "Pokud", "lemma": "pokud", "upos": "SCONJ", "xpos": "J,-------------", "feats": "_", "parent": null, "deprel": "mark", "deps": "[]", "misc": "_"}}
```

#### Rebind

The `rebind` action states that the token should be rebound to another token in the dependency structure. The `info` field contains the ID of the new parent token (numerical if referring to an already existing token, or a string with the prefix `new_` if referring to a newly-inserted token; see [Add](#add)).

```
PonkApp1:RuleTooLongExpressions:4bd3db28:rebind=9
```

# Rules, metrics, and profiles

