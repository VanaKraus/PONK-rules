from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

from typing import Annotated

from document_applicables import MINIMAL_CONLLU
from document_applicables.rules import Color

from server.api_helpers import *

app = FastAPI(
    title='PONK Rules', swagger_ui_parameters={"defaultModelsExpandDepth": 0}, openapi_url='/docs/openapi.json'
)


@app.get("/")
def root():
    return {"this is": "ponk-app1"}


@app.get("/docs/rules", response_class=HTMLResponse, tags=['visual'])
def rules_documentation():
    return Rule.generate_doc_html() + Rule.generate_doc_footer()


@app.get("/docs/metrics", response_class=HTMLResponse, tags=['visual'])
def metrics_documentation():
    return Metric.generate_doc_html() + Rule.generate_doc_footer()




class MainRequest(BaseModel):
    conllu_string: str = Field(examples=[MINIMAL_CONLLU])
    rule_list: list[RuleAPIWrapper] | None = None
    metric_list: list[MetricsWrapper] | None = None


class MainReply(BaseModel):
    modified_conllu: str = Field(examples=[MINIMAL_CONLLU])
    metrics: list[dict[str, float]] = Field(examples=[[{'sent_count': 1}, {'word_count': 3}]])
    rule_info: dict[str, dict[str, str | Color | dict | int | None]] = Field(
        examples=[
            {
                "RuleDoubleAdpos": {
                    "foreground_color": None,
                    "background_color": Color(123, 45, 67),
                    "cz_name": "Pravidlo dvojité obměny",
                    "en_name": "Double adposition rule",
                    "cz_doc": "Dokumentace pravidla",
                    "en_doc": "Rule documentation",
                    "cz_participants": {"adpos": "Adpozice s nejasnou valencí"},
                    "en_participants": {"adpos": "Adposition with an unclear valence"},
                    "order": 5,
                }
            }
        ]
    )
    metric_info: dict[str, dict[str, str | Color | dict | int | None]] = Field(
        examples=[
            {
                "smog": {
                    "cz_doc": "Měří čitelnost text v letech vzdělání nutných k pochopení textu.",
                    "cz_hint": "Používejte méně dlouhých slov a kratší věty/souvětí. Pište uvolněněji, méně technicky.",
                    "cz_name": "SMOG index",
                    "en_doc": "Measures readability in years of education necessary for successful understanding.",
                    "en_hint": "Use fewer long words, and shorter sentences. Make your writing more relaxed and less technical.",
                    "en_name": "SMOG index",
                    "intervals": {
                        "bad": [13.62265750478578, None],
                        "good": [None, 12.320016079839352],
                        "medium": [12.320016079839352, 13.62265750478578],
                    },
                    "order": 17,
                }
            },
            {
                "word_count": {
                    "cz_doc": "Počet slov v textu.",
                    "cz_hint": None,
                    "cz_name": "Počet slov",
                    "en_doc": "The count of words in the text.",
                    "en_hint": None,
                    "en_name": "Word Count",
                    "intervals": None,
                    "order": 21,
                }
            },
        ]
    )
    conflict_background_color: Color = Color(114, 114, 114)


def make_rule_info(rule_list: list[Rule]) -> dict[str, dict[str, str | Color | dict | int | None]]:
    return {
        rule.id(): {
            "order": ord,
            "foreground_color": rule.foreground_color,
            "background_color": rule.background_color,
            "cz_name": rule.cz_human_readable_name,
            "en_name": rule.en_human_readable_name,
            "cz_doc": rule.cz_doc,
            "en_doc": rule.en_doc,
            "cz_participants": rule.cz_paricipants,
            "en_participants": rule.en_paricipants,
        }
        for ord, rule in enumerate(rule_list)
        if rule.application_count != 0
    }


def make_metric_info(metric_list: list[Metric]) -> dict[str, dict[str, str | dict | int | None]]:
    return {
        metric.id(): {
            "order": ord,
            "cz_name": metric.cz_human_readable_name,
            "en_name": metric.en_human_readable_name,
            "cz_doc": metric.cz_doc,
            "en_doc": metric.en_doc,
            "cz_hint": metric.cz_hint if 'cz_hint' in metric.__dir__() else None,
            "en_hint": metric.en_hint if 'en_hint' in metric.__dir__() else None,
            'intervals': metric.intervals if 'intervals' in metric.__dir__() else None,
        }
        for ord, metric in enumerate(metric_list)
    }

# TODO: make the metric_list and rule_list fields intuitive
#       only then uncover the endpoint
# @app.post('/main', tags=['ponk_rules'])
def choose_stats_and_rules(main_request: MainRequest) -> MainReply:
    doc = try_build_conllu_from_string(main_request.conllu_string)
    metric_list = unwrap_metric_list(main_request.metric_list)
    rule_list = unwrap_rule_list(main_request.rule_list)
    metrics = compute_metrics(metric_list, doc)
    modified_doc = apply_rules(rule_list, doc)
    return MainReply(
        modified_conllu=modified_doc,
        metrics=metrics,
        rule_info=make_rule_info(rule_list),
        metric_info=make_metric_info(metric_list),
    )


@app.post('/raw', tags=['ponk_rules'])
def perform_defaults_on_conllu(file: UploadFile, profile: str = 'default') -> MainReply:
    doc = build_doc_from_upload(file)
    metric_list, rule_list = select_profile(profile)
    metrics = compute_metrics(metric_list, doc)
    modified_doc = apply_rules(rule_list, doc)
    return MainReply(
        modified_conllu=modified_doc,
        metrics=metrics,
        rule_info=make_rule_info(rule_list),
        metric_info=make_metric_info(metric_list),
    )


@app.post('/mattr-vis', response_class=HTMLResponse, tags=['ponk_rules', 'visual'])
def visualize_mattr(file: UploadFile, window_size: Annotated[int, Form()]):
    doc = build_doc_from_upload(file)
    return build_visualization_html(doc, window_size)


@app.get('/mattr-vis', response_class=HTMLResponse, tags=['ponk_rules', 'visual'])
def vizualize_ui():
    return """
    <form method='post' target='_self' enctype='multipart/form-data'>
        <label> Conllu:
            <input name='file' type=file>
        </label> <br>
        <label> Window size:
            <input name='window_size' type=number step=1 min=1 value='100'>
        </label><br>
        <button> Send </button>
    </form>
    """
