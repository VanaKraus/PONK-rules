from fastapi import FastAPI, UploadFile
from fastapi.responses import HTMLResponse
from io import TextIOWrapper

from pydantic import BaseModel, Field

from document_applicables import MINIMAL_CONLLU

from server.api_helpers import *

app = FastAPI(
    title='PONK Rules',
    swagger_ui_parameters={"defaultModelsExpandDepth": 0},
    openapi_url='/docs/openapi.json'
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


@app.post('/main', tags=['ponk_rules'])
def choose_stats_and_rules(main_request: MainRequest) -> MainReply:
    doc = try_build_conllu_from_string(main_request.conllu_string)
    metrics = compute_metrics(unwrap_metric_list(main_request.metric_list), doc)
    modified_doc = apply_rules(unwrap_rule_list(main_request.rule_list), doc)
    return MainReply(modified_conllu=modified_doc, metrics=metrics)


@app.post('/raw', tags=['ponk_rules'])
def perform_defaults_on_conllu(file: UploadFile, profile: str = 'default') -> MainReply:
    doc = build_doc_from_upload(file)
    metric_list, rule_list = select_profile(profile)
    metrics = compute_metrics(metric_list, doc)
    modified_doc = apply_rules(rule_list, doc)
    return MainReply(modified_conllu=modified_doc, metrics=metrics)


@app.post('/mattr-vis', response_class=HTMLResponse, tags=['ponk_rules', 'visual'])
def visualize_mattr(file: UploadFile):
    doc = build_doc_from_upload(file)
    return build_visualization_html(doc)


@app.get('/mattr-vis', response_class=HTMLResponse, tags=['ponk_rules', 'visual'])
def vizualize_ui():
    return """
    <form method='post' target='_self' enctype='multipart/form-data'>
        <label> Give conllu:
            <input name='file' type=file>
        </label> <br>
        <button> Send </button>
    </form>
    """
