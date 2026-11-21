"""Local structural schemas; native readers additionally verify all bindings."""


def object_schema(properties, *, optional=()):
    return dict(type='object', properties=properties,
        required=sorted(set(properties)-set(optional)), additionalProperties=False)


def schema(name):
    text = {'type': 'string'}
    sha = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
    obj = {'type': 'object'}
    boolean = {'type': 'boolean'}
    def array(item):
        return {'type': 'array', 'items': item}
    descriptor = object_schema(dict(contract_version={'const':'1.0.0'}, analyzer_id=text,
        adapter_version=text, capabilities=array(text), subject_modes=array(text), result_schema_version=text,
        execution_mode={'enum':['builtin_worker','external_result_only','future_unsupported']},
        determinism={'enum':['pinned_engine','not_guaranteed']},
        dependency_requirements=array(object_schema(dict(name=text, requirement=text))), extensions=obj))
    binding = object_schema(dict(descriptor=descriptor, descriptor_sha256=sha, capabilities=array(text)))
    inputs = object_schema(dict(analyzers=array(binding), settings=obj, context=array(obj), extensions=obj))
    subject = object_schema(dict(subject_key=sha, artifact_id=text, artifact_revision={'type':'integer','minimum':1},
        artifact_sha256=sha, field_pointer=text, value={}, value_sha256=sha,
        declared_language={'anyOf':[text, {'type':'null'}]}, normative_force=text), optional=('normative_force',))
    request = object_schema(dict(contract_version={'const':'1.0.0'}, request_id=text,
        snapshot_sha256=sha, analyzers=array(binding), subjects=array(subject), settings=obj,
        context=object_schema(dict(resources=array(obj), subject_keys=array(sha))), extensions=obj))
    report = object_schema(dict(contract_version={'const':'1.0.0'}, report_version={'const':'1.0.0'},
        run_id=text, request_id=text, snapshot_sha256=sha, analyzer=binding, engine=obj,
        subjects=array(obj), findings=array(obj), coverage=obj,
        run_status={'enum':['complete','partial','failed','unavailable']}, operational=obj,
        extensions=obj, result_sha256=sha))
    package = object_schema(dict(package_version={'const':'1.0.0'}, request=request, reports=array(report)))
    availability = object_schema(dict(known_builtin=boolean, descriptor_sha256=sha,
        execution_supported=boolean, availability={'enum':['not_implemented','not_checked','external_result_only']}))
    listing = object_schema(dict(format_version={'const':'1.0.0'}, analyzers=array(object_schema(dict(
        descriptor=descriptor, availability=availability, schemas={'type':'object','additionalProperties':obj},
        schema_scope={'const':'structural_shapes_native_binding_validation_required'})))))
    inspection = object_schema(dict(format_version={'const':'1.0.0'},
        sources=array(object_schema(dict(path=text, size={'anyOf':[{'type':'integer','minimum':0},{'type':'null'}]}, sha256={'anyOf':[sha,{'type':'null'}]},
            document={'anyOf':[obj, {'type':'null'}]}))), evaluation=obj,
        execution_complete=boolean, findings_failed=boolean, current_check_passed=boolean,
        gate_passed=boolean, approval_granted={'const':False}))
    return {'analyzer-descriptor-v1':descriptor, 'analyzer-inputs-v1':inputs,
        'analyzer-request-v1':request, 'analyzer-report-v1':report, 'analyzer-package-v1':package,
        'analyzer-directory-v1':listing, 'analyzer-inspection-v1':inspection}[name]
