# AI Email & Calendar Assistant

## Overview
The AI Email & Calendar Assistant is a local-first productivity application designed to help users manage email communication and scheduling workflows. The app connects to Gmail and Google Calendar, classifies incoming emails, generates AI-assisted reply drafts, detects meeting intent, and suggests calendar-based meeting options for quick response.

It is built as a FastAPI web application with PostgreSQL, OpenAI integration, Gmail API support, and Google Calendar scheduling features.



<p align="center">
  <img src="screenshots/Inbox Page.png" width="X"/>
  <img src="screenshots/Reply Draft Page.png" width="X"/>
  <img src="screenshots/Scheduling Signals Page.png" width="X"/>
</p>

### Inbox Page  
Displays recent Gmail messages in a categorized inbox view.  
Emails are labeled into categories such as important, meeting, newsletter, and review.

### Reply Draft Page  
Allows the user to preview an AI-generated draft response before creating a Gmail draft or sending an approved reply.

### Scheduling Signals  
Shows extracted scheduling details from a meeting-related email, including detected dates, times, ranges, and confidence score.

# Meeting Scheduling

<p align="center">
  <img src="screenshots/Suggested Meeting Options.png" width="X"/>
  <img src="screenshots/Meeting Length Selection.png" width="X"/>
  <img src="screenshots/Calendar Event Creation.png" width="X"/>
</p>

### Suggested Meeting Options  
For emails with scheduling intent, the system checks Google Calendar availability and generates suggested meeting slots.

### Meeting Length Selection  
Users can choose a meeting duration such as 15 minutes, 30 minutes, or 1 hour.  
Suggested time slots update dynamically based on the selected duration.

### Calendar Event Creation  
Once a meeting slot is selected, the user can create a calendar event directly from the reply workflow.

# Meeting Inbox

<p align="center">
  <img src="screenshots/Meeting Inbox Page.png" width="X"/>
  <img src="screenshots/Meeting Queue View.png" width="X"/>
</p>

### Meeting Inbox  
Meeting-related emails are stored in a dedicated sub-inbox so they remain accessible even after newer emails arrive.

### Meeting Queue Tracking  
Pending meeting threads stay in the queue until the user either replies or explicitly disregards them.

# Notifications

<p align="center">
  <img src="screenshots/Notification Demo.png" width="X"/>
  <img src="screenshots/Meeting Inbox Redirect.png" width="X"/>
</p>

### Browser Notifications  
The app polls for unresolved meeting-related emails during work hours and sends browser notifications while the app is open.

### Redirect Behavior  
If one unresolved meeting email exists, clicking the notification opens that thread directly.  
If multiple unresolved meeting emails exist, the notification redirects to the meeting inbox.

# Google Integration

<p align="center">
  <img src="screenshots/Google OAuth Connected.png" width="X"/>
  <img src="screenshots/Gmail Draft Created.png" width="X"/>
</p>

### Google OAuth  
Secure Google authentication is used to connect Gmail and Calendar access for the user.

### Gmail Draft Workflow  
Users can generate a reply draft, review it, create it as a Gmail draft, and optionally send it after approval.

# AI Classification and Drafting

## Email Processing Workflow

<p align="center">
  <img src="screenshots/Email Classification Demo.png" width="X"/>
  <img src="screenshots/AI Draft Demo.png" width="X"/>
</p>

**Email Classification Demo:**  
Incoming emails are analyzed and categorized to prioritize review and scheduling workflows.

**AI Draft Demo:**  
The system generates a suggested response that the user can review and approve before it is turned into a Gmail draft or sent.

# Settings

<p align="center">
  <img src="screenshots/App Configuration.png" width="X"/>
  <img src="screenshots/Work Hours Settings.png" width="X"/>
</p>

### App Configuration  
The project supports configurable work hours, meeting buffers, meeting durations, and timezone preferences.

### Work Hours Settings  
Notifications and scheduling logic respect configured working-hour boundaries and meeting availability rules.

## Technologies Used
- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Jinja2
- OpenAI API
- Gmail API
- Google Calendar API
- Google OAuth 2.0
- Uvicorn
- HTML/CSS
- JavaScript
- Git/GitHub

## Key Features
- Google OAuth integration for Gmail and Calendar access
- AI-assisted email classification
- AI-generated reply drafts with approval-first workflow
- Gmail draft creation and approved send flow
- Scheduling-intent extraction from meeting emails
- Calendar availability lookup and suggested meeting slots
- Selectable meeting duration options
- Persistent meeting sub-inbox and queue tracking
- Browser notifications for unresolved meeting emails
- Local-first architecture with configurable work hours and timezone support

## Project Status
In Progress  

This project is actively being developed with continued work on scheduling automation, notification reliability, and user workflow improvements.

## Author
Colin T.  
Computer Science Student  
Metropolitan State University of Denver
