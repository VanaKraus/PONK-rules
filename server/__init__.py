from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import HTMLResponse
from io import TextIOWrapper

from pydantic import BaseModel, Field
from typing import Annotated

from document_applicables import MINIMAL_CONLLU
from document_applicables.rules import Color

from server.api_helpers import *

app = FastAPI(
    title='PONK Rules', swagger_ui_parameters={"defaultModelsExpandDepth": 0}, openapi_url='/docs/openapi.json'
)


@app.get("/")
def root():
    return {"this is": "dog"}


@app.get("/docs/foo", response_class=HTMLResponse, tags=['visual'])
def asdf():
    return Rule.generate_doc_html() + Metric.generate_doc_html() + Rule.generate_doc_footer()


class MainRequest(BaseModel):
    conllu_string: str = Field(examples=[MINIMAL_CONLLU])
    rule_list: list[RuleAPIWrapper] | None = None
    metric_list: list[MetricsWrapper] | None = None


class MainReply(BaseModel):
    modified_conllu: str = Field(examples=[MINIMAL_CONLLU])
    metrics: list[dict[str, float]] = Field(examples=[[{'sent_count': 1}, {'word_count': 3}]])
    rule_info: dict[str, dict[str, str | Color | dict | None]] = Field(
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
                }
            }
        ]
    )
    conflict_background_color: Color = Color(114, 114, 114)


def make_rule_info(rule_list: list[Rule]) -> dict[str, dict[str, str | Color | dict | None]]:
    return {
        rule.id(): {
            "foreground_color": rule.foreground_color,
            "background_color": rule.background_color,
            "cz_name": rule.cz_human_readable_name,
            "en_name": rule.en_human_readable_name,
            "cz_doc": rule.cz_doc,
            "en_doc": rule.en_doc,
            "cz_participants": rule.cz_paricipants,
            "en_participants": rule.cz_paricipants,
        }
        for rule in rule_list
        if rule.application_count != 0
    }


@app.post('/main', tags=['ponk_rules'])
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
