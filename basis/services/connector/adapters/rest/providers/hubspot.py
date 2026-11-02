"""Shipped HubSpot CRM REST provider (entity streams; Batch 3)."""

from __future__ import annotations

from basis.services.connector.manifest.manifest_actions import entity_action_from_stream
from basis.services.connector.manifest.manifest_schema import (
    AuthSpec,
    CheckEndpointSpec,
    ConnectorManifest,
    DynamicSchemaLoaderSpec,
    OAuth2DialectSpec,
    PaginatorSpec,
    RetrieverSpec,
    StreamFieldSpec,
    StreamMutationSpec,
    StreamSpec,
)


def _companies_entity():
    stream = StreamSpec(
        name="companies",
        display_name="Companies",
        primary_key=["id"],
        cursor_field="updatedAt",
        default_label_field="properties.name",
        fields=[
            StreamFieldSpec(name="id", data_type="string", nullable=False, primary_key=True),
            StreamFieldSpec(name="properties.name", data_type="string"),
            StreamFieldSpec(name="properties.domain", data_type="string"),
            StreamFieldSpec(name="properties.industry", data_type="string"),
            StreamFieldSpec(name="properties.annualrevenue", data_type="number"),
            StreamFieldSpec(name="updatedAt", data_type="datetime"),
        ],
        dynamic_schema_loader=DynamicSchemaLoaderSpec(
            type="rest_metadata",
            metadata_path="/crm/v3/properties/companies",
            fields_field_path=["results"],
        ),
        retriever=RetrieverSpec(
            adapter="rest_declarative",
            http_method="GET",
            path="/crm/v3/objects/companies",
            records_field_path=["results"],
            paginator=PaginatorSpec(
                type="cursor",
                cursor_response_path="paging.next.after",
                cursor_request_param="after",
                page_size=100,
                limit_param="limit",
            ),
        ),
        mutations={
            "update": StreamMutationSpec(
                operation="update",
                adapter="rest_declarative",
                http_method="PATCH",
                path_template="/crm/v3/objects/companies/{{external_id}}",
                body_template={"properties": "{{patch}}"},
            ),
            "create": StreamMutationSpec(
                operation="create",
                adapter="rest_declarative",
                http_method="POST",
                path_template="/crm/v3/objects/companies",
                body_template={"properties": "{{patch}}"},
            ),
        },
    )
    return entity_action_from_stream(stream)


def _contacts_entity():
    stream = StreamSpec(
        name="contacts",
        display_name="Contacts",
        primary_key=["id"],
        cursor_field="updatedAt",
        default_label_field="properties.email",
        fields=[
            StreamFieldSpec(name="id", data_type="string", nullable=False, primary_key=True),
            StreamFieldSpec(name="properties.email", data_type="string"),
            StreamFieldSpec(name="properties.firstname", data_type="string"),
            StreamFieldSpec(name="properties.lastname", data_type="string"),
            StreamFieldSpec(name="properties.company", data_type="string"),
            StreamFieldSpec(name="updatedAt", data_type="datetime"),
        ],
        retriever=RetrieverSpec(
            adapter="rest_declarative",
            http_method="GET",
            path="/crm/v3/objects/contacts",
            records_field_path=["results"],
            paginator=PaginatorSpec(
                type="cursor",
                cursor_response_path="paging.next.after",
                cursor_request_param="after",
                page_size=100,
                limit_param="limit",
            ),
        ),
        mutations={
            "update": StreamMutationSpec(
                operation="update",
                adapter="rest_declarative",
                http_method="PATCH",
                path_template="/crm/v3/objects/contacts/{{external_id}}",
                body_template={"properties": "{{patch}}"},
            ),
            "create": StreamMutationSpec(
                operation="create",
                adapter="rest_declarative",
                http_method="POST",
                path_template="/crm/v3/objects/contacts",
                body_template={"properties": "{{patch}}"},
            ),
        },
    )
    return entity_action_from_stream(stream)


def _deals_entity():
    stream = StreamSpec(
        name="deals",
        display_name="Deals",
        primary_key=["id"],
        cursor_field="updatedAt",
        default_label_field="properties.dealname",
        fields=[
            StreamFieldSpec(name="id", data_type="string", nullable=False, primary_key=True),
            StreamFieldSpec(name="properties.dealname", data_type="string"),
            StreamFieldSpec(name="properties.amount", data_type="number"),
            StreamFieldSpec(name="properties.dealstage", data_type="string"),
            StreamFieldSpec(name="properties.pipeline", data_type="string"),
            StreamFieldSpec(name="updatedAt", data_type="datetime"),
        ],
        dynamic_schema_loader=DynamicSchemaLoaderSpec(
            type="rest_metadata",
            metadata_path="/crm/v3/properties/deals",
            fields_field_path=["results"],
        ),
        retriever=RetrieverSpec(
            adapter="rest_declarative",
            http_method="GET",
            path="/crm/v3/objects/deals",
            records_field_path=["results"],
            paginator=PaginatorSpec(
                type="cursor",
                cursor_response_path="paging.next.after",
                cursor_request_param="after",
                page_size=100,
                limit_param="limit",
            ),
        ),
        mutations={
            "update": StreamMutationSpec(
                operation="update",
                adapter="rest_declarative",
                http_method="PATCH",
                path_template="/crm/v3/objects/deals/{{external_id}}",
                body_template={"properties": "{{patch}}"},
            ),
            "create": StreamMutationSpec(
                operation="create",
                adapter="rest_declarative",
                http_method="POST",
                path_template="/crm/v3/objects/deals",
                body_template={"properties": "{{patch}}"},
            ),
        },
    )
    return entity_action_from_stream(stream)


def hubspot_manifest() -> ConnectorManifest:
    return ConnectorManifest(
        service="hubspot",
        display_name="HubSpot CRM",
        description="HubSpot CRM companies, contacts, and deals with incremental sync and property write-back.",
        categories=["CRM", "Sales", "Marketing"],
        homepage_url="https://www.hubspot.com",
        docs_url="https://developers.hubspot.com/docs/api/overview",
        auth=[
            AuthSpec(
                auth_mode="oauth2",
                base_url="https://api.hubapi.com",
                oauth2=OAuth2DialectSpec(
                    authorization_url="https://app.hubspot.com/oauth/authorize",
                    token_url="https://api.hubapi.com/oauth/v1/token",
                    scopes=[
                        "crm.objects.companies.read",
                        "crm.objects.companies.write",
                        "crm.objects.contacts.read",
                        "crm.objects.contacts.write",
                        "crm.objects.deals.read",
                        "crm.objects.deals.write",
                    ],
                ),
                check=CheckEndpointSpec(
                    method="GET",
                    path="/account-info/v3/details",
                    account_id_path="portalId",
                    display_name_path="uiDomain",
                ),
            ),
        ],
        actions=[_companies_entity(), _contacts_entity(), _deals_entity()],
    )
