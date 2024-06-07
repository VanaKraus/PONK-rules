from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from udapi.core.document import Document
from udapi.block.read.conllu import Conllu as ConlluReader
from io import FileIO, TextIOWrapper

from metrics import Metric, MetricsWrapper

from rules import Rule, RuleBlockWrapper, RuleAPIWrapper

from pydantic import BaseModel, Field

from utils import MINIMAL_CONLLU

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


def select_profile(profile_str: str) -> (list[Metric] | None , list[Rule] | None):
    # return appropriate set of rules and metrics based on the profiles selected
    # for now, just return the defaults
    print(f'Profile {profile_str} has been selected.')
    return None, None


def unwrap_metric_list(metric_wrapper_list: list[MetricsWrapper] | None):
    if metric_wrapper_list is None:
        return metric_wrapper_list
    return [item.metric for item in metric_wrapper_list]


def unwrap_rule_list(rule_wrapper_list: list[RuleAPIWrapper] | None):
    if rule_wrapper_list is None:
        return rule_wrapper_list
    return [item.rule for item in rule_wrapper_list]


def compute_metrics(metric_list: list[Metric] | None, doc: Document) -> list[dict[str, float]]:
    if metric_list is None:
        # return all available metrics
        metric_list = [subclass() for subclass in Metric.get_final_children()]
    return [{metric.metric_id: metric.apply(doc)} for metric in metric_list]


def apply_rules(rule_list: list[Rule] | None, doc: Document) -> str:
    if rule_list is None:
        rule_list = [rule() for rule in Rule.get_final_children()]
    for rule in rule_list:
        RuleBlockWrapper(rule).run(doc)
    return doc.to_conllu_string()


def try_build_conllu_from_string(conllu_string: str) -> Document:
    doc = Document()
    try:
        doc.from_conllu_string(string=conllu_string)
    except ValueError:
        raise HTTPException(status_code=422, detail='Conllu string validation failed.')
    return doc


@app.post('/main', tags=['ponk_rules'])
def choose_stats_and_rules(main_request: MainRequest) -> MainReply:
    doc = try_build_conllu_from_string(main_request.conllu_string)
    metrics = compute_metrics(unwrap_metric_list(main_request.metric_list), doc)
    modified_doc = apply_rules(unwrap_rule_list(main_request.rule_list), doc)
    return MainReply(modified_conllu=modified_doc, metrics=metrics)


@app.post('/raw', tags=['ponk_rules'])
def perform_defaults_on_conllu(file: UploadFile, profile: str = 'default'):
    reader = ConlluReader(filehandle=TextIOWrapper(file.file))
    doc = Document()
    reader.apply_on_document(doc)
    metric_list, rule_list = select_profile(profile)
    metrics = compute_metrics(metric_list, doc)
    modified_doc = apply_rules(rule_list, doc)
    return MainReply(modified_conllu=modified_doc, metrics=metrics)


# @app.post("/upload", status_code=201)
# def receive_conllu(file: UploadFile):
#     # read uploaded file
#     file_id = os.urandom(8).hex()
#     filename = file_id + ".conllu"
#     with open(filename, "wb") as local_copy:
#         local_copy.write(file.file.read())
#     try:
#         Document(filename=filename)
#         return {"file_id": file_id}
#     except ValueError as e:
#         local_copy.close()
#         os.remove(filename)
#         raise HTTPException(status_code=406, detail=f"{type(e).__name__}: {str(e)}")
#
#
# @app.post("/stats/{text_id}")
# def get_stats_for_conllu(text_id: str, metric_list: list[MetricsWrapper] | None = None):
#     # return statistics for a given id
#     doc = get_doc_from_id(text_id)
#     return compute_metrics(metric_list, doc)
#
#
# @app.get("/rules/{text_id}")
# def get_conllu_after_rules_applied(text_id: str, rule_list: list[RuleAPIWrapper] | None = None):
#     # return modified conllu after application of rules
#     doc = get_doc_from_id(text_id)
#     return apply_rules(rule_list, doc)
#
#
# def get_doc_from_id(doc_id: str):
#     try:
#         doc = Document(filename=doc_id + ".conllu")
#         return doc
#     except ValueError:
#         raise HTTPException(status_code=404)
