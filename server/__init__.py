from fastapi import FastAPI, UploadFile
from fastapi.responses import HTMLResponse
from udapi.block.read.conllu import Conllu as ConlluReader
from io import TextIOWrapper

from pydantic import BaseModel, Field

from utils import MINIMAL_CONLLU

from server.api_helpers import *

app = FastAPI(
    title='PONK Rules',
    swagger_ui_parameters={"defaultModelsExpandDepth": 0},
    openapi_url='/docs/openapi.json'
)


@app.get("/")
def root():
    return {"this is": "dog"}


@app.get("/docs/foo", response_class=HTMLResponse)
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
    reader = ConlluReader(filehandle=TextIOWrapper(file.file))
    doc = Document()
    reader.apply_on_document(doc)
    metric_list, rule_list = select_profile(profile)
    metrics = compute_metrics(metric_list, doc)
    modified_doc = apply_rules(rule_list, doc)
    return MainReply(modified_conllu=modified_doc, metrics=metrics)
