"""Provider-enforced JSON shapes. Semantic evidence checks remain in pipeline."""
def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
def array(items):return {'type':'array','items':items}
TEXT={'type':'string'}
BOOL={'type':'boolean'}
STRINGS=array(TEXT)
EVIDENCE_ITEM=obj({'sourceId':TEXT,'passageId':TEXT})
SCHEMAS={
    'planning':obj({'safe':BOOL,'reason':TEXT,'scope':TEXT,'queries':STRINGS}),
    'source_selection':obj({'ids':{'type':'array','items':TEXT,'minItems':18,'maxItems':18}}),
    'evidence':obj({'sufficient':BOOL,'gaps':STRINGS,
        'sources':array(obj({'id':TEXT,'originGroup':TEXT,'kind':{'type':'string','enum':['primary','reporting','analysis']},'independenceNote':TEXT})),
        'claims':array(obj({'id':TEXT,'finding':TEXT,'state':{'type':'string','enum':['supported','disputed','attributed']},'evidence':array(EVIDENCE_ITEM),'caveat':TEXT}))}),
    'drafting':obj({'title':TEXT,'answer':TEXT,'sections':array(obj({'heading':TEXT,'paragraphs':array(obj({'text':TEXT,'claimIds':STRINGS}))})),
        'unknowns':STRINGS,'limitations':STRINGS}),
    'verification':obj({'approved':BOOL,'issues':STRINGS,'supportedClaimIds':STRINGS,'independentOrigins':{'type':'integer'},'primarySourcePresent':BOOL}),
}
