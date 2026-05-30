# AI Email & Calendar Assistant

## Overview
The AI Email & Calendar Assistant is a local-first productivity application designed to help users manage email communication and meeting scheduling workflows. The app connects to Gmail and Google Calendar, classifies incoming emails, generates AI-assisted reply drafts, detects meeting intent, and suggests calendar-based meeting options for quick response.

It is built as a FastAPI web application with PostgreSQL, OpenAI integration, Gmail API support, and Google Calendar scheduling features.

# Inbox Views

### Main Inbox  
Displays recent Gmail messages in a categorized inbox view.  
Emails are labeled into categories such as important, meeting, newsletter, and review.

<p align="center">
  <img src="screenshots/Main Inbox.png" width="x"/>
</p>

### Meeting Inbox  
Meeting-related emails are stored in a dedicated sub-inbox so they remain accessible even after newer emails arrive.  
Pending meeting threads stay in the queue until the user either replies or explicitly disregards them.

<p align="center">
  <img src="screenshots/Meeting Inbox.png" width="x"/>
</p>

# Reply Draft Workflow

### Reply Draft – Selected Email  
Shows the connected account and selected email, including sender, message content, and detected category tag.

<p align="center">
  <img src="screenshots/Reply Draft prt. 1.png" width="x"/>
</p>

### Reply Draft – Scheduling Signals  
Displays extracted scheduling information from a meeting-related email, including:
- Requested duration
- Dates mentioned
- Times mentioned
- Time ranges
- Timezone clues

<p align="center">
  <img src="screenshots/Reply Draft prt. 2.png" width="x"/>
</p>

### Reply Draft – AI Generated Response  
Shows the automatically generated AI reply that the user can review before creating or sending a draft.

<p align="center">
  <img src="screenshots/Reply Draft prt. 5.png" width="x"/>
</p>

# Suggested Meeting Options

### 15-Minute Meeting Suggestions  
Shows suggested meeting slots when the meeting length is set to 15 minutes.

<p align="center">
  <img src="screenshots/Reply Draft prt. 3.png" width="x"/>
</p>

### 30-Minute Meeting Suggestions  
Shows updated suggested meeting slots when the meeting length is changed to 30 minutes, demonstrating dynamic slot regeneration based on duration selection.

<p align="center">
  <img src="screenshots/Reply Draft prt. 4.png" width="x"/>
</p>

# Gmail Draft and Send Flow

### Send Approved Draft Button  
Appears once a Gmail draft has been created and is ready for approval-based sending.

<p align="center">
  <img src="screenshots/Send approved draft button.png" width="x"/>
</p>

### Gmail Draft Creation  
Shows the draft being successfully created inside Gmail.

<p align="center">
  <img src="screenshots/Email Draft Creation.png" width="x"/>
</p>

### Email Response Received  
Demonstrates the generated response being delivered to the recipient.

<p align="center">
  <img src="screenshots/Email Response Recieved.png" width="x"/>
</p>

# Calendar Integration

### Calendar Event Created  
Shows the confirmation prompt after a calendar event is created, including the Google Calendar link.

<p align="center">
  <img src="screenshots/Calendar Event created.png" width="x"/>
</p>

### Google Calendar Event View  
Shows the created calendar event inside Google Calendar with its associated scheduling details.

<p align="center">
  <img src="screenshots/Calendar Event.png" width="x"/>
</p>

# Notifications

<p align="center">
  <img src="screenshots/Email meetings reminder notification.png" width="280"/>
</p>

### Meeting Reminder Notification  
The app sends browser notifications for unresolved meeting-related emails during configured work hours.  
If one meeting thread is pending, the notification opens that email directly.  
If multiple meeting threads are pending, the notification redirects the user to the meeting inbox.

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
- HTML/CSS
- JavaScript
- Uvicorn
- Git/GitHub

## Key Features
- Google OAuth integration for Gmail and Calendar access
- AI-assisted email classification
- AI-generated reply drafts with approval-first workflow
- Gmail draft creation and approved send flow
- Scheduling-intent extraction from meeting emails
- Calendar availability lookup and suggested meeting slots
- Dynamic meeting duration selection
- Persistent meeting sub-inbox and queue tracking
- Browser notifications for unresolved meeting emails
- Local-first architecture with configurable work hours and timezone support

## Project Status
In Progress

This project is actively being developed with continued improvements to scheduling automation, notification reliability, and workflow usability.

## Author
Colin M.  
Computer Science Student  
Metropolitan State University of Denver
