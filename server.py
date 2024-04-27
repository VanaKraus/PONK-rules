from fastapi import FastAPI, HTTPException, UploadFile
from udapi.core.document import Document
from udapi.block.read.conllu import Conllu as ConlluReader
from io import FileIO, TextIOWrapper

from metrics import Metric, MetricsWrapper

from rules import Rule, RuleBlockWrapper, RuleAPIWrapper

from pydantic import BaseModel, Field

from utils import MINIMAL_CONLLU

app = FastAPI(
    title='PONK Rules',
    swagger_ui_parameters={"defaultModelsExpandDepth": 0}
)


@app.get("/")
def root():
    return {"this is": "dog"}


class MainRequest(BaseModel):
    conllu_string: str = Field(examples=[MINIMAL_CONLLU])
    rule_list: list[RuleAPIWrapper] | None = None
    metric_list: list[MetricsWrapper] | None = None


class MainReply(BaseModel):
    modified_conllu: str = Field(examples=[MINIMAL_CONLLU])
    metrics: list[dict[str, float]] = Field(examples=[[{'sent_count': 1}, {'word_count': 3}]])


def compute_metrics(metric_list: list[MetricsWrapper] | None, doc: Document) -> list[dict[str, float]]:
    if metric_list is None:
        # return all available metrics
        return [{instance.metric_id: instance.apply(doc)} for instance in
                [subclass() for subclass in Metric.get_final_children()]]
    return [{metric.metric_id: metric.apply(doc)} for metric in [x.metric for x in metric_list]]


def apply_rules(rule_list: list[RuleAPIWrapper] | None, doc: Document) -> str:
    rules = [rule() for rule in Rule.get_final_children()] if rule_list is None else [item.rule for item in rule_list]
    for rule in rules:
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
    metrics = compute_metrics(main_request.metric_list, doc)
    modified_doc = apply_rules(main_request.rule_list, doc)
    return MainReply(modified_conllu=modified_doc, metrics=metrics)


@app.post('/raw', tags=['ponk_rules'])
def perform_defaults_on_conllu(file: UploadFile):
    reader = ConlluReader(filehandle=TextIOWrapper(file.file))
    doc = Document()
    reader.apply_on_document(doc)
    metrics = compute_metrics(None, doc)
    modified_doc = apply_rules(None, doc)
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
