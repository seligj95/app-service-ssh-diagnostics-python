@description('Name of the existing Azure OpenAI account')
param openAiAccountName string

@description('Principal ID of the web app system-assigned identity')
param webPrincipalId string

@description('Optional principal ID for the developer running azd up; granted the same role for local-dev convenience')
param userPrincipalId string = ''

resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: openAiAccountName
}

// Built-in role: "Cognitive Services OpenAI User"
var openAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource webRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: openAi
  name: guid(openAi.id, webPrincipalId, openAiUserRoleId)
  properties: {
    principalId: webPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions', openAiUserRoleId
    )
  }
}

resource userRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(userPrincipalId)) {
  scope: openAi
  name: guid(openAi.id, userPrincipalId, openAiUserRoleId)
  properties: {
    principalId: userPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions', openAiUserRoleId
    )
  }
}
