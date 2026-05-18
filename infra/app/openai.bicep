@description('Name of the Azure OpenAI account')
param name string
param location string = resourceGroup().location
param tags object = {}

@description('Chat deployment used by /chat')
param chatDeployment string = 'gpt-4o-mini'

@description('Capacity (TPM/1000) for the chat deployment')
param chatCapacity int = 30

resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

resource chat 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: chatDeployment
  sku: {
    name: 'GlobalStandard'
    capacity: chatCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o-mini'
      version: '2024-07-18'
    }
  }
}

output name string = openAi.name
output id string = openAi.id
output endpoint string = openAi.properties.endpoint
output deploymentName string = chat.name
