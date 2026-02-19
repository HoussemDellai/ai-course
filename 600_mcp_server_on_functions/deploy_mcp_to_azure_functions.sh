# src: https://learn.microsoft.com/en-us/azure/azure-functions/how-to-create-function-azure-cli?tabs=go%2Clinux%2Cbash%2Cazure-cli&pivots=programming-language-python

# In a terminal or command prompt, run this func init command to create a function app project in the current folder:

func init --worker-runtime python

# Use this func new command to add a function to your project:

func new --name HttpExample --template "HTTP trigger" --authlevel "function"

# After you've successfully created your function app in Azure, you're now ready to deploy your local functions project by using the func azure functionapp publish command.
# In your root project folder, run this func azure functionapp publish command:

func azure functionapp publish function-app-600 --build remote