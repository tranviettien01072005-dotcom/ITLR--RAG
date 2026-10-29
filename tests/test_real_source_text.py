import pandas as pd
from itlr.pipelines.build_embeddings_v2 import build_text

def test_real_fulltext_preserves_exact_source_case():
    row = pd.Series(dict(title='Python', category='Programming', topics='python', description='short', full_text='Exact Source Text: Lists preserve order.'))
    assert build_text(row) == row['full_text']

def test_lexical_index_includes_source_body_beyond_description():
    from itlr.core.recommender import build_field_corpus
    rows=pd.DataFrame([dict(title='Guide',category='Web',topics='web',type='Tài liệu',instructor='Docs',platform='Official',description='Intro',full_text='UniqueParserEvidence')])
    assert 'uniqueparserevidence' in build_field_corpus(rows,'full')[0]

def test_index_catalog_keeps_evidence_provenance():
    from itlr.pipelines.build_model import index_catalog
    rows=pd.DataFrame([dict(item_id=1,title='Docs',type='Tài liệu',description='source',category='Web',topics='web',instructor='Docs',platform='Official',link='https://example.org',origin='crawl:official',full_text='Exact evidence',crawl_license='MIT')])
    result=index_catalog(rows)
    assert result.iloc[0]['full_text']=='Exact evidence'
    assert result.iloc[0]['origin']=='crawl:official'
