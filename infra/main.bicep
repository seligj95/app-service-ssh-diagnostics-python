targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Id of the user or app to assign application roles')
param principalId string = ''

@description('Python runtime version on App Service')
param pythonVersion string = '3.14'

@description('SKU of the App Service plan')
param appServicePlanSkuName string = 'P0v3'

@description('Chat model deployment used by /chat')
param chatModelDeployment string = 'gpt-4o-mini'

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = {
  'azd-env-name': environmentName
}

module monitoring './shared/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    logAnalyticsName: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    applicationInsightsName: '${abbrs.insightsComponents}${resourceToken}'
    location: location
    tags: tags
  }
}

module appServicePlan './shared/app-service-plan.bicep' = {
  name: 'app-service-plan'
  params: {
    name: '${abbrs.webServerFarms}${resourceToken}'
    location: location
    tags: tags
    skuName: appServicePlanSkuName
    reserved: true
  }
}

module openai './app/openai.bicep' = {
  name: 'openai'
  params: {
    name: '${abbrs.cognitiveServicesAccounts}${resourceToken}'
    location: location
    tags: tags
    chatDeployment: chatModelDeployment
  }
}

module web './app/web.bicep' = {
  name: 'web'
  params: {
    name: '${abbrs.webSitesAppService}web-${resourceToken}'
    location: location
    tags: tags
    appServicePlanId: appServicePlan.outputs.id
    pythonVersion: pythonVersion
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    azureOpenAiEndpoint: openai.outputs.endpoint
    azureOpenAiDeployment: chatModelDeployment
  }
}

module openaiRbac './app/openai-rbac.bicep' = {
  name: 'openai-rbac'
  params: {
    openAiAccountName: openai.outputs.name
    webPrincipalId: web.outputs.principalId
    userPrincipalId: principalId
  }
}

output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output WEB_URI string = web.outputs.uri
output WEB_NAME string = web.outputs.name
output AZURE_OPENAI_ENDPOINT string = openai.outputs.endpoint
output AZURE_OPENAI_DEPLOYMENT string = chatModelDeployment
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.applicationInsightsConnectionString
