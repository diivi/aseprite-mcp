# Aseprite MCP Tools
[![Trust Score](https://archestra.ai/mcp-catalog/api/badge/quality/diivi/aseprite-mcp)](https://archestra.ai/mcp-catalog/diivi__aseprite-mcp)

A Python module that serves as an MCP server for interacting with the Aseprite API

Demo where Cursor draws a cloud in aseprite using the MCP:

https://github.com/user-attachments/assets/572edf75-ab66-4700-87ee-d7d3d196c597


## Installation:
```json
{
  "mcpServers": {
      "aseprite": {
          "command": "/opt/homebrew/bin/uv",
          "args": [
              "--directory",
              "/path/to/repo",
              "run",
              "-m",
              "aseprite_mcp"
          ]
      }
  }
}
```
