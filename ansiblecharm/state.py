from charmhelpers.core import hookenv
import os
import six
import yaml


def juju_state_to_yaml(yaml_path, namespace_separator=':',
                       allow_hyphens_in_keys=True, mode=None):
    """Update the juju config and state in a yaml file.

    This includes any current relation-get data, and the charm
    directory.

    This function was created for the ansible and saltstack
    support, as those libraries can use a yaml file to supply
    context to templates, but it may be useful generally to
    create and update an on-disk cache of all the config, including
    previous relation data.

    By default, hyphens are allowed in keys as this is supported
    by yaml, but for tools like ansible, hyphens are not valid [1].

    [1] http://www.ansibleworks.com/docs/playbooks_variables.html#what-makes-a-valid-variable-name
    """
    config = hookenv.config()

    config['charm_dir'] = os.environ.get('CHARM_DIR', '')
    config['local_unit'] = hookenv.local_unit()
    config['service_name'] = hookenv.service_name()
    config['unit_private_address'] = hookenv.unit_private_ip()
    config['unit_public_address'] = hookenv.unit_get('public-address')

    # Don't use non-standard tags for unicode which will not
    # work when salt uses yaml.load_safe.
    yaml.add_representer(six.text_type,
                         lambda dumper, value: dumper.represent_scalar(
                             six.u('tag:yaml.org,2002:str'), value))

    yaml_dir = os.path.dirname(yaml_path)
    if not os.path.exists(yaml_dir):
        os.makedirs(yaml_dir)

    if os.path.exists(yaml_path):
        with open(yaml_path, "r") as existing_vars_file:
            existing_vars = yaml.load(existing_vars_file.read())
    else:
        with open(yaml_path, "w+"):
            pass
        existing_vars = {}

    if mode is not None:
        os.chmod(yaml_path, mode)

    if not allow_hyphens_in_keys:
        config = dict_keys_without_hyphens(config)
    existing_vars.update(config)

    update_relations(existing_vars, namespace_separator)

    with open(yaml_path, "w+") as fp:
        fp.write(yaml.dump(existing_vars, default_flow_style=False))


def dict_keys_without_hyphens(a_dict):
    """Return the a new dict with underscores instead of hyphens in keys."""
    return dict(
        (key.replace('-', '_'), val) for key, val in a_dict.items())


def update_relations(context, namespace_separator=':'):
    """Update the context with the relation data."""
    # Add any relation data prefixed with the relation type.
    relation_type = hookenv.relation_type()
    relations = []
    context['current_relation'] = {}
    if relation_type is not None:
        relation_data = hookenv.relation_get()
        context['current_relation'] = relation_data
        # Deprecated: the following use of relation data as keys
        # directly in the context will be removed.
        relation_data = dict(
            ("{relation_type}{namespace_separator}{key}".format(
                relation_type=relation_type,
                key=key,
                namespace_separator=namespace_separator), val)
            for key, val in relation_data.items())
        relation_data = dict_keys_without_hyphens(relation_data)
        context.update(relation_data)
        relations = hookenv.relations_of_type(relation_type)
        relations = [dict_keys_without_hyphens(rel) for rel in relations]

    context['relations_full'] = hookenv.relations()

    # the hookenv.relations() data structure is effectively unusable in
    # templates and other contexts when trying to access relation data other
    # than the current relation. So provide a more useful structure that works
    # with any hook.
    local_unit = hookenv.local_unit()
    relations = {}
    for rname, rids in context['relations_full'].items():
        relations[rname] = []
        for rid, rdata in rids.items():
            data = rdata.copy()
            if local_unit in rdata:
                data.pop(local_unit)
            for unit_name, rel_data in data.items():
                new_data = {'__relid__': rid, '__unit__': unit_name}
                new_data.update(rel_data)
                relations[rname].append(new_data)
    context['relations'] = relations
