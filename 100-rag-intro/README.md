# create Azure AI Search using Azure CLI
# 1. Create a resource group
az group create -n rg-openai -l swdencentral

# 2. Create a search service
az search service create -n ai-search-swc -g rg-openai --sku standard

# 3. Get the admin key
az search admin-key show --service-name ai-search-swc -g rg-openai

# 4. Get the query key
az search query-key list --service-name ai-search-swc -g rg-openai
