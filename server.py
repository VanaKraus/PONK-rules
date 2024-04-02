import os
from math import log2
from typing import Iterator, Tuple

from fastapi import FastAPI, UploadFile, HTTPException
from udapi.core.document import Document
from udapi.core.node import Node

import rules

app = FastAPI()

@app.get("/")
def root():
  return {"this is": "dog"}

@app.post("/upload", status_code=201)
def receive_conllu(file: UploadFile):
  #read uploaded file
  file_id = os.urandom(8).hex()
  filename = file_id + ".conllu"
  with open(filename, "wb") as local_copy:
    local_copy.write(file.file.read())
  try:
    doc = Document(filename=filename)
    return {"file_id": file_id}
  except ValueError as e:
    local_copy.close()
    os.remove(filename)
    raise HTTPException(status_code=406, detail=f"{type(e).__name__}: {str(e)}")

@app.get("/stats/{text_id}")
def get_stats_for_conllu(text_id: str):
  #return statistics for a given id
  doc = get_doc_from_id(text_id)
  filtered_nodes = list(node for node in doc.nodes if node.upos != "PUNCT")
  sentences = len(list(doc.trees))
  words = len(filtered_nodes)
  chars = sum(len(node.form) for node in filtered_nodes)
  return {
    "id": text_id,
    "sents": sentences,
    "words": words,
    "chars": chars,
    "CLI": 0.047 * (chars/words) * 100 - 0.286 * (sentences/words) * 100 - 12.9,
    "ARI": 3.666 * (chars/words) + 0.631 * (words/sentences) - 19.491, #formula in Cinkova 2021 has parens switched
    "num_hapax": count_hapaxes(filtered_nodes, use_lemma=True),
    "entropy": compute_entropy(filtered_nodes, use_lemma=True)
  }

@app.get("/rules/{text_id}")
def get_conllu_after_rules_applied(text_id: str):
  #return modified conllu after application of rules
  doc = get_doc_from_id(text_id)
  rules.double_adpos_rule().run(doc)
  return {"id": text_id, "document": doc.to_conllu_string()}

def get_doc_from_id(id: str):
  try:
    doc = Document(filename=id + ".conllu")
    return doc
  except ValueError:
    raise HTTPException(status_code=404)

def get_word_counts(nodes: list[Node], use_lemma = False) -> Iterator[Tuple[str, int]]:
  all_words = list(node.form if not use_lemma else node.lemma for node in nodes)
  unique_words = set(all_words)
  counts = map(lambda x: all_words.count(x), unique_words)
  return zip(unique_words,counts)

def count_hapaxes(nodes: list[Node], use_lemma = False):
  counts = [item[1] for item in get_word_counts(nodes, use_lemma)]
  return counts.count(1)

def compute_entropy(nodes: list[Node], use_lemma = False):
  counts = [item[1] for item in get_word_counts(nodes, use_lemma)]
  n_words = sum(counts)
  probs = map(lambda x: x/n_words, counts)
  return -sum(prob * log2(prob) for prob in probs)
