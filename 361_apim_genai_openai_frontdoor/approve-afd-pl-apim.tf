# output "apim_private_endpoint_connection_name" {
#   value = azapi_resource.apim.output.properties.privateEndpointConnections.0.name
# }

# output "apim_private_endpoint_connection_id" {
#   value = azapi_resource.apim.output.properties.privateEndpointConnections.0.id
# }

# # RESPONSE 400: 400 Bad Request
# # ERROR CODE: ApproveOrRejectPrivateEndpointConnectionBadRequest
# # --------------------------------------------------------------------------------
# # {
# #   "error": {
# #     "code": "ApproveOrRejectPrivateEndpointConnectionBadRequest",
# #     "message": "Private Endpoint Connection Request ID is unexpected null.",
# #     "details": null,
# #     "innerError": null
# #   }
# # }
# # Approve Frontdoor's private endpoint connection to APIM
# resource "azapi_update_resource" "approve-private-link-frontdoor-origin" {
#   type        = "Microsoft.ApiManagement/service/privateEndpointConnections@2024-05-01"
# #   resource_id = azapi_resource.apim.output.properties.privateEndpointConnections.0.id
#   name        = azapi_resource.apim.output.properties.privateEndpointConnections.0.name
#   parent_id   = azapi_resource.apim.id

#   body = {
#     properties = {
#       privateLinkServiceConnectionState = {
#         status      = "Approved"
#         description = "Approved automatically by Terraform"
#       }
#     }
#   }

#   depends_on = [azapi_update_resource.configure-private-link-frontdoor-origin]
# }
