# ProjectPlanner API Documentation

---

## Table of Contents

- [ProjectPlanner Documentation](#projectplanner-api-documentation)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [API Endpoints](#api-endpoints)
    - [1. User Management Endpoints](#1-user-management-endpoints)
      - [1.1. Register User (Username/Password)](#11-register-user-usernamepassword)
      - [1.2. Register with Google](#12-register-with-google)
      - [1.3. Login (Username/Password)](#13-login-usernamepassword)
      - [1.4. Refresh Token](#14-refresh-token)
      - [1.5. Logout (Client-side)](#15-logout-client-side)
      - [1.6. Get User Profile](#16-get-user-profile)
      - [1.7. Update User Profile](#17-update-user-profile)
      - [1.8. Request Password Reset](#18-request-password-reset)
      - [1.9. Confirm Password Reset](#19-confirm-password-reset)
      - [1.10. Change Password (Logged-in User)](#110-change-password-logged-in-user)
      - [1.11. Update RBAC roles](#111-update-rbac-roles)
    - [2. Project and Board Management Endpoints](#2-project-and-board-management-endpoints)
      - [2.1 List Projects](#21-list-projects)
      - [2.2. Create Project](#22-create-project)
      - [2.3. Get Project Summary](#23-get-project-summary)
      - [2.4. Get Project Timeline](#24-get-project-timeline)
      - [2.5. Get Project Backlog](#25-get-project-backlog)
      - [2.6. Get Project Board](#26-get-project-board)
      - [2.7. Get Project Calendar](#27-get-project-calendar)
      - [2.8. Get Project List](#28-get-project-list)
      - [2.9. Get Project Development](#29-get-project-development)
      - [2.10. Get Archived Work](#210-get-archived-work)
      - [2.11. Get Project Settings](#211-get-project-settings)
      - [2.12. Update Project Settings](#212-update-project-settings)
    - [3. Sprint Operations Endpoints](#3-sprint-operations-endpoints)
      - [3.1 Create Sprint](#31-create-sprint)
      - [3.2. Update Sprint](#32-update-sprint)
      - [3.3. Start Sprint](#33-start-sprint)
      - [3.4. Complete Sprint](#34-complete-sprint)
      - [3.5. Get Project Sprints](#35-get-project-sprint)
      - [3.6. Get Sprint Issues](#36-get-sprint-issues)
      - [3.7. Create Sprint Issues](#37-create-sprint-issues)
    - [3. Issue Operations Endpoints](#3-issue-operations-endpoints)
      - [3.1. Create Issue](#31-create-issue)
      - [3.2. Get Issue Details](#32-get-issue-details)
      - [3.3. Update Issue Details](#33-update-issue-details)
      - [3.4. Move Issue Status](#34-move-issue-status)
      - [3.5. List Issue Comments](#35-list-issue-comments)
      - [3.6. Add Issue Comment](#36-add-issue-comment)
      - [3.7. Bulk Update Issues](#37-bulk-update-issues)
      - [3.8. Bulk Delete Issues](#38-bulk-delete-issues)
    - [4. Artificial Intelligence Endpoints](#4-artificial-intelligence-endpoints)
      - [4.1. Semantic Issue Search](#41-semantic-issue-search)
      - [4.2. AI Project Assistant](#42-ai-project-assistant)
      - [4.3. Issue Summary Generation](#43-issue-summary-generation)
    - [5. Attachment Management Endpoints](#5-attachment-management-endpoints)
      - [5.1. Request Upload URL](#51-request-upload-url)
      - [5.2. Confirm Upload Completion](#52-confirm-upload-completion)
      - [5.3. Get Attachment Preview](#53-get-attachment-preview)
      - [5.4. List Issue Attachments](#54-list-issue-attachments)
    - [6. Notification Endpoints](#6-notification-endpoints)
      - [6.1. Get Unread Count](#61-get-unread-count)
      - [6.2. Connect to Notification Stream](#62-connect-to-notification-stream)
      - [6.3. Mark All as Read](#63-mark-all-as-read)
    - [7. Analytics Endpoints](#7-analytics-endpoints)
      - [7.1. Get Velocity Chart](#71-get-velocity-chart)
      - [7.2. Get Burn-down Data](#72-get-burn-down-data)
      - [7.3. AI Predicted Bottlenecks](#73-ai-predicted-bottlenecks)
  - [Environment Variables](#environment-variables)

---

## Overview

This document outlines the API endpoints for the **ProjectPlanner** service. ProjectPlanner allows users to:

1. **User Management**
   1. Create user accounts via standard credentials or Google OAuth
   2. Secure sessions using JWT authentication with refresh token support
   3. Manage user profiles and Role-Based Access Control (RBAC)

2. **Project and Board Management**
   1. Create projects and visualize workflows through Timelines, Backlogs, and Kanban Boards
   2. Access specialized views including project calendars and development tracking
   3. Manage project lifecycles by archiving work and updating global settings

3. **Issue Operations**
   1. Create and track individual tasks (Issues) with detailed descriptions
   2. Manage workflow stages by moving issues across status columns
   3. Foster collaboration through threaded comments on specific tasks

4. **Artificial Intelligence**
   1. Execute Semantic Search to find information based on intent rather than just keywords
   2. Use "Ask AI" for natural language querying of project data
   3. Generate instant ticket summaries and receive real-time streaming AI responses

5. **Attachment Management**
   1. Request secure upload URLs for file handling
   2. Store and preview attachments linked directly to project issues
   3. Maintain a organized list of all assets associated with specific tasks

6. **Notifications**
   1. Track unread activity counts across projects
   2. Connect to a real-time notification stream for instant updates
   3. Perform bulk actions like marking all alerts as read

7. **Analytics**
   1. Monitor team performance with Velocity Charts and Burn-down data
   2. Leverage AI to predict and identify potential project bottlenecks
   3. Access data-driven insights to optimize sprint planning

The platform features integrated **Website Title Extraction**, which automatically pulls metadata from external URLs shared within the system to provide better context for team members.

---

## API Endpoints

### 1. User Management Endpoints

#### 1.1. Register User (Username/Password)

**Purpose:** Create a new user account with username and password.

**Endpoint:** `/auth/register`

**Method:** `POST`

**Request Body:**

```json
{
  "username": "henry_dev",
  "email": "henry@example.com",
  "password": "securepassword123"
}
```

**Response:** (201 Created)

```json
{
  "id": 42,
  "username": "henry_dev",
  "email": "henry@example.com",
  "created_at": "2026-05-29T14:30:00Z"
}
```

---

#### 1.2. Register with Google

**Purpose:** Create a new user account with Google authentication.

**Endpoint:** `/auth/google`

**Method:** `POST`

**Request Body:**

```json
{
  "token": "google_oauth_token"
}
```

**Response:** (201 Created)

```json
{
  "id": 43,
  "username": "henry_dev",
  "email": "henry@example.com",
  "created_at": "2026-05-29T14:35:00Z",
  "auth_provider": "google"
}
```

---

#### 1.3. Login (Username/Password)

**Purpose:** Authenticate user and get JWT access token and refresh token.

**Endpoint:** `/auth/login`

**Method:** `POST`

**Request Body:**

```json
{
  "username": "henry_dev",
  "password": "securepassword123"
}
```

**Response:** (200 OK)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 42,
    "username": "henry_dev",
    "email": "henry@example.com",
    "roles": ["Admin", "Developer"]
  }
}
```

---

#### 1.4. Refresh Token

**Purpose:** Get a new access token using a refresh token.

**Endpoint:** `/auth/refresh`

**Method:** `POST`

**Request Body:**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:** (200 OK)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

#### 1.5. Logout (Client-side)

**Purpose:** Client removes tokens from storage. No server-side action required with pure JWT.

**Note:** In a pure JWT implementation, logout is handled client-side by removing the tokens from storage. The frontend application should delete both the access token and refresh token from localStorage or cookies when the user logs out, and then redirect to the login page.

---

#### 1.6. Get User Profile

**Purpose:** Retrieve current user profile information.

**Endpoint:** `/users/me`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
{
  "id": 42,
  "username": "henry_dev",
  "involved_projects": [
    {
      "project_id": "proj_101",
      "name": "Cloud Migration",
      "role": "Admin",
      "active_tasks": 5
    },
    {
      "project_id": "proj_202",
      "name": "API Gateway Redesign",
      "role": "Developer",
      "active_tasks": 2
    }
  ]
}
```

---

#### 1.7. Update User Profile

**Purpose:** Update user profile information.

**Endpoint:** `/users/me`

**Method:** `PATCH`

**Headers:**

- `Authorization: Bearer {access_token}`

**Request Body:**

```json
{
  "username": "henry_updated",
  "email": "new_henry@example.com"
}
```

**Response:** (200 OK)

```json
{
  "id": 42,
  "username": "henry_updated",
  "email": "new_henry@example.com",
  "created_at": "2026-05-29T14:30:00Z"
}
```

---

#### 1.8. Request Password Reset

**Purpose:** Start a password-reset flow by sending a reset link to the user’s email.

**Endpoint:** `/auth/password-reset/request`

**Method:** `POST`

**Request Body:**

```json
{
  "email": "henry@example.com",
  "username": "henry_dev"
}
```

**Response:** (200 OK)

```json
{
  "message": "Password reset email sent."
}
```

---

#### 1.9. Confirm Password Reset

**Purpose:** Complete password reset using the token sent by email.

**Endpoint:** `/auth/password-reset/confirm`

**Method:** `POST`

**Request Body:**

```json
{
  "token": "abcdef1234567890",
  "new_password": "NewP@ssw0rd!"
}
```

**Response:** (200 OK)

```json
{
  "message": "Password has been reset successfully."
}
```

---

#### 1.10. Change Password (Logged-in User)

**Purpose:** Allow a signed-in user to update their password.

**Endpoint:** `/users/me/password`

**Method:** `PATCH`

**Headers:**

- `Authorization: Bearer {access_token}`

**Request Body:**

```json
{
  "current_password": "OldP@ss1",
  "new_password": "NewP@ssw0rd!"
}
```

**Response:** (200 OK)

```json
{
  "message": "Password changed successfully."
}
```

---

#### 1.11. Update RBAC Roles

**Purpose:** Assign or modify organizational roles and permissions for a specific user. (Admin only)

**Endpoint:** `/users/{id}/roles`

**Method:** `PATCH`

**Headers:**

- `Authorization: Bearer {access_token}`

**Request Body:**

```json
{
  "roles": ["Admin", "ProjectManager", "Developer"]
}
```

**Response:** (200 OK)

```json
{
  "id": 42,
  "username": "henry_dev",
  "current_roles": ["Admin", "ProjectManager"],
  "updated_at": "2026-05-29T14:30:00Z"
}
```

---

### 2. Project and Board Management Endpoints

#### 2.1. List Projects

**Purpose:** Retrieve all projects that the authenticated user has access to. This is used to populate the project switcher and the main dashboard.

**Endpoint:** `/projects`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
[
  {
    "id": "proj_101",
    "name": "Cloud Infrastructure Migration",
    "key": "CIM",
    "lead": {
      "id": 88,
      "username": "lydiagao"
    },
    "issue_count": 42,
    "created_at": "2026-01-15T09:00:00Z"
  },
  {
    "id": "proj_105",
    "name": "Frontend Design System",
    "key": "FDS",
    "lead": {
      "id": 42,
      "username": "henry_dev"
    },
    "issue_count": 12,
    "created_at": "2026-03-10T14:30:00Z"
  }
]
```

---

#### 2.2. Create Project

**Purpose:** Initialize a new project workspace.

**Endpoint:** `/projects`

**Method:** `POST`

**Headers:**

- `Authorization: Bearer {access_token}`

**Request Body:**

```json
{
  "name": "Cloud Infrastructure Migration",
  "key": "CIM",
  "description": "Moving legacy architecture to a secure microservices model."
}
```

**Response:** (201 Created)

```json
{
  "id": "proj_101",
  "name": "Cloud Infrastructure Migration",
  "key": "CIM",
  "description": "Moving legacy architecture to a secure microservices model.",
  "owner_id": 42,
  "created_at": "2026-05-29T10:00:00Z"
}
```

---

#### 2.3. Get Project Summary

**Purpose:** Retrieve a high-level KPI and status breakdown of a project's overall health.

**Endpoint:** `/projects/{project_id}/summary`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
{
  "project_id": "proj_101",
  "name": "Cloud Infrastructure Migration",
  "status": "Active",
  "stats": {
    "open_issues": 24,
    "completed_issues": 115,
    "team_count": 8,
    "days_remaining": 45
  }
}
```

---

#### 2.4. Get Project Timeline

**Purpose:** Retrieve the milestones, roadmap, and scheduled releases for the project.

**Endpoint:** `/projects/{project_id}/timeline`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
{
  "project_id": "proj_101",
  "milestones": [
    {
      "id": "m_01",
      "title": "Database Schema Finalized",
      "due_date": "2026-06-15",
      "status": "In Progress"
    },
    {
      "id": "m_02",
      "title": "Alpha Deployment",
      "due_date": "2026-07-20",
      "status": "Scheduled"
    }
  ]
}
```

---

#### 2.5. Get Project Backlog

**Purpose:** List all unassigned, un-sprinted, or planned issues within a project.

**Endpoint:** `/projects/{project_id}/backlog`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
[
  {
    "issue_key": "CIM-402",
    "title": "Configure Kafka KRaft mode",
    "type": "Task",
    "priority": "High",
    "created_at": "2026-05-28T11:20:00Z"
  },
  {
    "issue_key": "CIM-405",
    "title": "Implement Redis cache-aside logic",
    "type": "Task",
    "priority": "Medium",
    "created_at": "2026-05-29T09:15:00Z"
  }
]
```

---

#### 2.6. Get Project Board

**Purpose:** Retrieve the column configurations and card layout for the Kanban/Scrum interactive board.

**Endpoint:** `/projects/{project_id}/board`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
{
  "project_id": "proj_101",
  "columns": [
    {
      "id": "col_todo",
      "name": "To Do",
      "issues": [
        {
          "issue_key": "CIM-12",
          "title": "Setup VPC Peering",
          "priority": "High",
          "issue_type": "Task",
          "assignee": null
        }
      ]
    },
    {
      "id": "col_progress",
      "name": "In Progress",
      "issues": [
        {
          "issue_key": "CIM-10",
          "title": "Write Dockerfiles",
          "priority": "Medium",
          "issue_type": "Story",
          "assignee": {
            "id": 42,
            "username": "henry_dev",
            "avatar_url": "https://api.planner.com/static/avatars/h_dev.png"
          }
        }
      ]
    },
    {
      "id": "col_done",
      "name": "Done",
      "issues": []
    }
  ]
}
```

---

#### 2.7. Get Project Calendar

**Purpose:** Fetch all date-bound tasks, sprint deadlines, and launch events organized chronologically by date.

**Endpoint:** `/projects/{project_id}/calendar`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
{
  "project_id": "proj_101",
  "events": [
    {
      "id": "ev_1",
      "title": "Sprint 3 Review",
      "start_time": "2026-06-05T15:00:00Z",
      "end_time": "2026-06-05T16:00:00Z",
      "type": "Meeting"
    },
    {
      "id": "ev_2",
      "title": "CIM-88 Due Date",
      "start_time": "2026-06-10T23:59:59Z",
      "end_time": "2026-06-10T23:59:59Z",
      "type": "Issue Deadline"
    }
  ]
}
```

---

#### 2.8. Get Project List

**Purpose:** Retrieve the flat list of issues belonging to a specific project to populate the "List" tab view. Supports column-based filtering, sorting, and pagination.

**Endpoint:** `/projects/{project_id}/list`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Query Parameters:**

- `status`: String (e.g., "IN PROGRESS", "TO DO")

- `priority`: String (e.g., "Medium", "High")

- `assignee_id`: Integer

- `search`: String (for the search input field)

**Response:** (200 OK)

```json
{
  "project_id": "proj_101",
  "project_key": "CIM",
  "issues": [
    {
      "issue_key": "CIM-402",
      "title": "Configure Kafka KRaft mode",
      "assignee": "henry_dev",
      "reporter": "henry_dev",
      "priority": "High",
      "status": "IN PROGRESS",
      "resolution": "Unresolved",
      "created_at": "2026-05-28T11:20:00Z",
      "updated_at": "2026-05-29T09:15:00Z"
    },
    {
      "issue_key": "CIM-405",
      "title": "Implement Redis cache-aside logic",
      "assignee": "Unassigned",
      "reporter": "henry_dev",
      "priority": "Medium",
      "status": "TO DO",
      "resolution": "Unresolved",
      "created_at": "2026-05-29T09:15:00Z",
      "updated_at": "2026-05-29T09:15:00Z"
    }
  ]
}
```

---

#### 2.9. Get Project Development

**Purpose:** Retrieve integrations, repository URLs, build/deployment statuses, and CI/CD pipelines connected to the project workspace.

**Endpoint:** `/projects/{project_id}/development`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
{
  "project_id": "proj_101",
  "repository": {
    "provider": "GitHub",
    "name": "cloud-migration-service",
    "url": "https://github.com/org/cloud-migration-service",
    "is_connected": true
  },
  "latest_builds": [
    {
      "build_number": "741",
      "branch": "main",
      "status": "Success",
      "commit_sha": "7a3f12b",
      "finished_at": "2026-05-29T18:45:00Z"
    }
  ]
}
```

---

#### 2.10. Get Archived Work

**Purpose:** Access historic, archived issues, epics, or completed sprint history no longer active on the live boards.

**Endpoint:** `/projects/{project_id}/archive`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
[
  {
    "id": "arch_09",
    "type": "Sprint 1 Archive",
    "archived_at": "2026-04-12T17:00:00Z",
    "summary": "Completed 18 infrastructure assessment stories."
  }
]
```

---

#### 2.11. Get Project Settings

**Purpose:** Fetch the raw configuration data for a project to populate admin forms.

**Endpoint:** `/projects/{project_id}/settings`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
{
  "project_id": "proj_101",
  "name": "Cloud Infrastructure Migration",
  "is_public": false,
  "default_assignee_id": 42,
  "allow_guest_comments": true,
  "notification_level": "High"
}
```

---

#### 2.12. Update Project Settings

**Purpose:** Modify structural options, visibility settings, or set fallback configurations for a specific project.

**Endpoint:** `/projects/{project_id}/settings`

**Method:** `PATCH`

**Headers:**

- `Authorization: Bearer {access_token}`

**Request Body:**

```json
{
  "is_public": true,
  "notification_level": "Medium"
}
```

**Response:** (200 OK)

```json
{
  "message": "Project settings updated successfully."
}
```

---

### 3. Sprint Operations Endpoints

### 3.1 Create Sprint

Creates a new sprint within a specific project. Sprints are typically created in a future state.

Request Body
JSON

{
"name": "Sprint 1",
"goal": "Complete the user authentication module",
"startDate": "2026-06-15T09:00:00Z",
"endDate": "2026-06-29T17:00:00Z"
}

Responses

    201 Created: Sprint successfully created. Returns the created sprint object.

    400 Bad Request: Invalid request payload.

    404 Not Found: Project ID not found.

### 3.2 Update Sprint

Updates the details of an existing sprint.

    Endpoint: PUT /api/v1/sprints/{sprintId}

    Content-Type: application/json

Path Parameters
Parameter Type Description
sprintId string The unique identifier of the sprint.

Request Body
JSON

{
"name": "Sprint 1 - Updated",
"goal": "Complete user auth and basic profile views",
"startDate": "2026-06-15T09:00:00Z",
"endDate": "2026-06-29T17:00:00Z"
}

Responses

    200 OK: Sprint successfully updated.

    400 Bad Request: Invalid parameters provided.

    404 Not Found: Sprint ID not found.

### 3.3 Start Sprint

Transitions a sprint from a future state to an active state.

    Endpoint: POST /api/v1/sprints/{sprintId}/start

    Content-Type: application/json

Path Parameters
Parameter Type Description
sprintId string The unique identifier of the sprint to start.

Responses

    200 OK: Sprint successfully started.

    400 Bad Request: Sprint is already active or closed, or lacks required fields (like a start date).

    404 Not Found: Sprint ID not found.

### 3.4 Complete Sprint

Transitions an active sprint to a closed state. Usually requires defining where incomplete issues should be moved.

    Endpoint: POST /api/v1/sprints/{sprintId}/complete

    Content-Type: application/json

Path Parameters
Parameter Type Description
sprintId string The unique identifier of the sprint.

Request Body
Field Type Description
moveToBacklog boolean If true, incomplete issues go to the backlog.
destinationSprintId string (Optional) The ID of the next sprint to move incomplete issues to.

Request Example
JSON

{
"moveToBacklog": false,
"destinationSprintId": "spr_98765"
}

Responses

    200 OK: Sprint successfully closed.

    400 Bad Request: Sprint is not currently active.

    404 Not Found: Sprint ID not found.

### 3.5 Get Project Sprints

Retrieves a list of all sprints associated with a specific project.

    Endpoint: GET /api/v1/projects/{projectId}/sprints

Path Parameters
Parameter Type Description
projectId string The unique identifier of the project.

Query Parameters
Parameter Type Description
state string (Optional) Filter by sprint state: active, future, or closed.
limit integer (Optional) Number of results to return. Default is 50.

Responses

    200 OK: Returns an array of sprint objects.

JSON

{
"data": [
{
"id": "spr_12345",
"name": "Sprint 1",
"state": "active",
"projectId": "proj_111"
}
],
"total": 1
}

### 3.6 Get Sprint Issues

Retrieves all issues (tasks, bugs, stories) currently assigned to a specific sprint.

    Endpoint: GET /api/v1/sprints/{sprintId}/issues

Path Parameters
Parameter Type Description
sprintId string The unique identifier of the sprint.

Responses

    200 OK: Returns an array of issue objects.

JSON

{
"data": [
{
"issueId": "iss_1001",
"title": "Create login page",
"status": "in_progress",
"storyPoints": 5
}
],
"total": 1
}

### 3.7 Create Sprint Issues

Adds or assigns existing issues to a specific sprint. (Note: If your system allows creating brand new issues directly inside a sprint rather than moving them, this endpoint might accept standard issue payload objects instead).

    Endpoint: POST /api/v1/sprints/{sprintId}/issues

    Content-Type: application/json

Path Parameters
Parameter Type Description
sprintId string The unique identifier of the sprint.

Request Body
JSON

{
"issueIds": [
"iss_1001",
"iss_1002"
]
}

Responses

    201 Created (or 200 OK): Issues successfully added to the sprint.

    400 Bad Request: One or more issue IDs are invalid.

    404 Not Found: Sprint ID not found.

---

### 3. Issue Operations Endpoints

#### 3.1. Create Issue

**Purpose:** Initialize a new work item (Task, Bug, Story) within a specific project.

**Endpoint:** `/issues/`

**Method:** `POST`

**Headers:**

- `Authorization: Bearer {access_token}`

**Request Body:**

```json
{
  "project_id": "proj_101",
  "title": "Configure Kafka KRaft mode",
  "issue_type": "Task",
  "priority": "High",
  "description": "Migration from Zookeeper to KRaft for the event bus.",
  "assignee_id": 42
}
```

**Response:** (201 Created)

```json
{
  "issue_key": "CIM-402",
  "title": "Configure Kafka KRaft mode",
  "description": "Migration from Zookeeper to KRaft for the event bus.",
  "issue_type": "Task",
  "priority": "High",
  "status": "TO DO",
  "assignee": {
    "id": 42,
    "username": "henry_dev",
    "avatar_url": "https://api.planner.com/static/avatars/h_dev.png"
  },
  "reporter": {
    "id": 88,
    "username": "lydiagao",
    "avatar_url": "https://api.planner.com/static/avatars/lydia.png"
  },
  "created_at": "2026-05-29T20:45:00Z",
  "updated_at": "2026-05-29T20:45:00Z"
}
```

---

#### 3.2. Get Issue Details

**Purpose:** Retrieve full metadata and history for a specific issue.

**Endpoint:** `/issues/{issue_key}`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
{
  "issue_key": "CIM-402",
  "title": "Configure Kafka KRaft mode",
  "description": "Migration from Zookeeper to KRaft for the event bus.",
  "issue_type": "Task",
  "priority": "High",
  "status": "TO DO",
  "assignee": {
    "id": 42,
    "username": "henry_dev",
    "avatar_url": "https://api.planner.com/static/avatars/h_dev.png"
  },
  "reporter": {
    "id": 88,
    "username": "lydiagao",
    "avatar_url": "https://api.planner.com/static/avatars/lydia.png"
  },
  "created_at": "2026-05-29T20:45:00Z",
  "updated_at": "2026-05-29T20:45:00Z"
}
```

---

#### 3.3. Update Issue Details

**Purpose:** Modify attributes of a specific issue such as status, priority, or assignee.

**Endpoint:** `/issues/{issue_key}`

**Method:** `PATCH`

**Headers:**

- `Authorization: Bearer {access_token}`

**Request Body:**

```json
{
  "status": "IN REVIEW",
  "priority": "Medium"
}
```

**Response:** (201 Created)

```json
{
  "issue_key": "CIM-402",
  "status": "IN REVIEW",
  "priority": "Medium",
  "updated_at": "2026-05-29T21:15:00Z",
  "modified_by": "henry_dev"
}
```

---

#### 3.4. Move Issue Status

**Purpose:** Dedicated endpoint for board transitions; handles state-change logic like setting resolutions.

**Endpoint:** `/issues/{issue_key}/status`

**Method:** `PUT`

**Headers:**

- `Authorization: Bearer {access_token}`

**Request Body:**

```json
{
  "status": "DONE"
}
```

**Response:** (201 Created)

```json
{
  "issue_key": "CIM-402",
  "status": "DONE",
  "resolution": "Fixed",
  "resolved_at": "2026-05-29T21:20:00Z"
}
```

---

#### 3.5. List Issue Comments

**Purpose:** Retrieve the threaded conversation for a specific issue.

**Endpoint:** `/issues/{issue_key}/comments`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
[
  {
    "comment_id": 501,
    "content": "The Redis cache-aside logic is passing.",
    "author": { "username": "henry_dev", "avatar_url": "..." },
    "created_at": "2026-05-29T21:25:00Z"
  }
]
```

#### 3.6. Add Issue Comment

**Purpose:** Retrieve the threaded conversation for a specific issue.

**Endpoint:** `/issues/{issue_key}/comments`

**Method:** `POST`

**Headers:**

- `Authorization: Bearer {access_token}`

**Request Body:**

```json
{
  "content": "I've updated the Kafka producer settings."
}
```

**Response:** (200 OK)

```json
{
  "comment_id": 502,
  "content": "I've updated the Kafka producer settings.",
  "author": { "username": "henry_dev", "avatar_url": "..." },
  "created_at": "2026-05-29T21:48:00Z"
}
```

#### 3.7. Bulk Update Issues

**Purpose:** Modify multiple issues at once (e.g., from the List view).

**Endpoint:** `/issues/bulk`

**Method:** `PATCH`

**Headers:**

- `Authorization: Bearer {access_token}`

**Request Body:**

```json
{
  "issue_keys": ["CIM-402", "CIM-405"],
  "updates": { "status": "IN REVIEW" }
}
```

**Response:** (200 OK)

```json
{
  "summary": {
    "total": 2,
    "success_count": 1,
    "failure_count": 1
  },
  "results": [
    {
      "issue_key": "CIM-402",
      "status": "Updated",
      "updated_at": "2026-05-29T21:55:00Z"
    },
    {
      "issue_key": "CIM-405",
      "status": "Failed",
      "error": "Issue is currently locked by another user"
    }
  ]
}
```

---

#### 3.8. Bulk Delete Issues

**Purpose:** Batch removal of issues.

**Endpoint:** `/issues/bulk`

**Method:** `DELETE`

**Headers:**

- `Authorization: Bearer {access_token}`

**Request Body:**

```json
{
  "issue_keys": ["CIM-402", "CIM-405"]
}
```

**Response:** (204 No Content)

---

### 4. Artificial Intelligence Endpoints

#### 4.1. Semantic Issue Search

**Purpose:** Search for issues using natural language queries. Unlike standard keyword search, this uses vector embeddings to find relevant tasks even if the exact words don't match (e.g., searching "database lag" finds "Optimize Redis caching").

**Endpoint:** `/ai/search`

**Method:** `POST`

**Headers:**

- `Authorization: Bearer {access_token}`

**Request Body:**

```json
{
  "project_id": "proj_101",
  "query": "problems with message bus performance",
  "limit": 5
}
```

**Response:** (200 OK)

```json
{
  "query": "problems with message bus performance",
  "results": [
    {
      "issue_key": "CIM-402",
      "title": "Configure Kafka KRaft mode",
      "score": 0.92,
      "summary": "Migration to KRaft to improve metadata performance."
    },
    {
      "issue_key": "CIM-415",
      "title": "Investigate producer latency",
      "score": 0.85,
      "summary": "High latency observed in event-driven messaging service."
    }
  ]
}
```

---

#### 4.2. AI Project Assistant

**Purpose:** An interactive chat endpoint that answers questions about project status, blockers, or history. This uses Server-Sent Events (SSE) to stream the response back for a "typing" effect.

**Endpoint:** `/barcode/{barcode_id}/image`

**Method:** `POST`

**Headers:**

- `Authorization: Bearer {access_token}`
- `Accept: text/event-stream`

**Request Body:**

```json
{
  "project_id": "proj_101",
  "message": "Which tasks are currently blocking the Kafka migration?",
  "stream": true
}
```

**Response:**

- 200 Stream of data chunks

---

#### 4.3. Issue Summary Generation

**Purpose:** Automatically generate a concise summary or "TL;DR" for an issue that has a long comment history.

**Endpoint:** `/ai/summarize/{issue_key}`

**Method:** `POST`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
{
  "issue_key": "CIM-402",
  "summary": "The team is migrating Kafka to KRaft mode to remove Zookeeper dependency. Henry is currently debugging producer latency issues in the dev environment.",
  "generated_at": "2026-05-29T22:10:00Z"
}
```

---

### 5. Attachment Management Endpoints

#### 5.1. Request Upload URL

**Purpose:** Obtain a temporary, pre-signed URL to upload a file directly to cloud storage. This keeps file traffic off your main application server.

**Endpoint:** `/attachments/upload-url`

**Method:** `POST`

**Headers:**

- `Authorization: Bearer {access_token}`

**Request Body:**

```json
{
  "issue_key": "CIM-402",
  "file_name": "architecture_diagram.png",
  "content_type": "image/png"
}
```

**Response:** (200 OK)

```json
{
  "upload_url": "https://storage.googleapis.com/planner-assets/temp-12345?signature=...",
  "file_id": "file_uuid_998",
  "expires_at": "2026-05-29T22:30:00Z"
}
```

---

#### 5.2. Confirm Upload Completion

**Purpose:** Notify the backend that the file has been successfully uploaded to the cloud. The backend then attaches the file record to the issue and moves it from "temp" to "permanent" storage.

**Endpoint:** `/attachments/confirm`

**Method:** `POST`

**Headers:**

- `Authorization: Bearer {access_token}`

**Request Body:**

```json
{
  "file_id": "file_uuid_998",
  "status": "success"
}
```

**Response:** (200 OK)

```json
{
  "issue_key": "CIM-402",
  "attachment": {
    "id": "file_uuid_998",
    "file_name": "architecture_diagram.png",
    "size_bytes": 1048576,
    "uploaded_at": "2026-05-29T22:15:00Z"
  }
}
```

---

#### 5.3. Get Attachment Preview

**Purpose:** Generate a secure, short-lived link to view or download an attachment. For images, this often points to a "thumbnail" version.

**Endpoint:** `/attachments/{file_id}/preview`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
{
  "file_id": "file_uuid_998",
  "download_url": "https://storage.googleapis.com/planner-assets/perm/architecture_diagram.png?token=...",
  "thumbnail_url": "https://storage.googleapis.com/planner-assets/thumbs/architecture_diagram_sm.png",
  "expires_in_seconds": 3600
}
```

---

#### 5.4. List Issue Attachments

**Purpose:** Get a list of all files currently attached to a specific issue.

**Endpoint:** `/issues/{issue_key}/attachments`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
[
  {
    "id": "file_uuid_998",
    "file_name": "architecture_diagram.png",
    "content_type": "image/png",
    "size_kb": 1024,
    "uploaded_by": "henry_dev",
    "uploaded_at": "2026-05-29T22:15:00Z"
  },
  {
    "id": "file_uuid_441",
    "file_name": "logs.txt",
    "content_type": "text/plain",
    "size_kb": 12,
    "uploaded_by": "lydiagao",
    "uploaded_at": "2026-05-28T10:05:00Z"
  }
]
```

---

### 6. Notification Endpoints

#### 6.1. Get Unread Count

**Purpose:** Fetch the current number of unread notifications to display as a "badge" count (e.g., the little red number over a bell icon) in the navigation bar.

**Endpoint:** `/notifications/unread-count`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
{
  "unread_count": 3,
  "last_checked_at": "2026-05-29T22:15:00Z"
}
```

---

#### 6.2. Connect to Notification Stream

**Purpose:** Establish a persistent, real-time connection. Instead of polling every 10 seconds, the server "pushes" new notifications to the client the moment they happen.

**Endpoint:** `/notifications/stream`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

- `Accept: text/event-stream`

- `Cache-Control: no-cache`

- `Connection: keep-alive`

**Response:**

- 200 Stream of data chunks

---

#### 6.3. Mark All as Read

**Purpose:** Clear the unread status for all notifications belonging to the current user. This is typically triggered when the user opens the notification panel.

**Endpoint:** `/notifications/read-all`

**Method:** `POST`

**Headers:**

- `Authorization: Bearer {access_token}`

**Response:** (200 OK)

```json
{
  "status": "success",
  "marked_count": 3,
  "timestamp": "2026-05-29T22:25:00Z"
}
```

---

### 7. Analytics Endpoints

#### 7.1. Get Short URL Analytics

**Purpose:** Retrieve the amount of work (usually in Story Points) the team completes in each sprint. This helps in predicting how much work can be handled in future iterations.

**Endpoint:** `/analytics/velocity`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Query Parameters:**

- `period=day|week|month|year` - Time period for analytics (default: month)
- `start_date=YYYY-MM-DD` - Start date for custom range (optional)
- `end_date=YYYY-MM-DD` - End date for custom range (optional)

**Response:**

```json (200 OK)
{
  "project_id": "proj_101",
  "period_type": "month",
  "range": {
    "start": "2026-01-01",
    "end": "2026-05-29"
  },
  "data": [
    {
      "label": "2026-01",
      "completed_count": 45,
      "story_points": 120
    },
    {
      "label": "2026-02",
      "completed_count": 38,
      "story_points": 110
    },
    {
      "label": "2026-03",
      "completed_count": 52,
      "story_points": 145
    }
  ],
  "totals": {
    "total_completed": 135,
    "average_per_period": 45
  }
}
```

---

#### 7.2. Get Burn-down Data

**Purpose:** Track the total work remaining in the current sprint. This endpoint provides the "Ideal" line versus the "Actual" remaining work.

**Endpoint:** `/analytics/burndown`

**Method:** `GET`

**Headers:**

- `Authorization: Bearer {access_token}`

**Query Parameters:**

- `sprint_id={id}` - sprint for analytics (default: current)

**Response:** (200 OK)

```json
{
  "sprint_id": "spr_55",
  "start_date": "2026-05-15",
  "end_date": "2026-05-30",
  "data_points": [
    { "date": "2026-05-15", "ideal_remaining": 100, "actual_remaining": 100 },
    { "date": "2026-05-16", "ideal_remaining": 90, "actual_remaining": 95 },
    { "date": "2026-05-17", "ideal_remaining": 80, "actual_remaining": 75 }
  ]
}
```

---

#### 7.3. AI Predicted Bottlenecks

**Purpose:** Use an LLM to analyze the current distribution of tasks and identify likely delays (e.g., too many issues stuck in "In Review" or an overloaded assignee).

**Endpoint:** `/analytics/ai-bottlenecks`

**Method:** `POST`

**Headers:**

- `Authorization: Bearer {access_token}`

**Request Body:**

```json
{
  "project_id": "proj_101",
  "include_historical_data": true
}
```

**Response:**

```json
{
  "bottlenecks": [
    {
      "type": "Stage Congestion",
      "location": "In Review",
      "severity": "High",
      "insight": "There are 8 tickets currently in 'In Review' with only 1 developer assigned as a reviewer. This is likely to delay the sprint goal."
    },
    {
      "type": "Resource Overload",
      "location": "User: henry_dev",
      "severity": "Medium",
      "insight": "Henry has 15 story points assigned for the next 3 days. Average completion rate suggests a 20% overflow risk."
    }
  ],
  "generated_at": "2026-05-29T22:30:00Z"
}
```

---

## Environment Variables

The application requires the following environment variables to be set:

| Variable           | Description                          | Default                            |
| ------------------ | ------------------------------------ | ---------------------------------- |
| DATABASE_URL       | Full PostgreSQL connection string    | Host=localhost;Database=cim_dev... |
| REDIS_URL          | Redis connection for caching/pub-sub | localhost:6379                     |
| KAFKA_BROKERS      | List of Kafka broker addresses       | localhost:9092                     |
| JWT_SECRET         | Secret key for signing JWTs          | None                               |
| JWT_ACCESS_EXPIRE  | Access token expiration in seconds   | 3600 (1 hour)                      |
| JWT_REFRESH_EXPIRE | Refresh token expiration in seconds  | 604800 (7 days)                    |
| AI_API_KEY         | API key for LLM services             | None                               |
