---
name: morning-briefing
description: Generate a comprehensive morning briefing with world news, tech, unrestricted models, weather, email, calendar, and system status
always: true
---

# Morning Briefing Skill

Generate a comprehensive, lengthy morning briefing covering all of the user's interests. This skill aggregates information from multiple sources and presents findings in a structured format.

## Trigger

- **Command**: `/goodmorning` (from Telegram or CLI)
- **Keywords**: "morning briefing", "daily briefing", "good morning"

## Topics to Cover

The briefing MUST include ALL of the following sections:

### 1. World News
- Fetch from BBC News (https://www.bbc.com/news) and other major sources
- Include top 3-5 breaking headlines
- Provide brief summaries of each

### 2. Tech & AI News
- Search for latest AI/tech news using `web_search`
- Include major announcements, product releases, and trends
- Topics: AI models, big tech, regulations, industry moves

### 3. Unrestricted Models (LLMs)
- Search for trending uncensored models on HuggingFace
- Include: Dolphin, EverythingLM, AI Power, other popular uncensored models
- Mention new releases and interesting models
- Use `web_search` to find "uncensored LLM models huggingface 2026"

### 4. Weather - Quakers Hill, NSW, Australia
- Use wttr.in for weather data
- Command: `curl -s "wttr.in/Quakers+Hill,+NSW,+Australia?format=%l:+%c+%t+feels+like+%f+humidity+%h+wind+%w+UV+%u+rain+%p"`
- Include: current temp, feels like, humidity, wind, UV index, rain chance
- Add forecast if available

### 5. Email Status
- Use Gmail skill to scan inbox
- Command: `scan inbox` or check last scan results in `/home/nanobot/gmail/`
- Summarize: unread count, important emails, any action needed

### 6. Calendar
- Check Google Calendar for today's events
- Use: `list events` or similar
- Include: meetings, appointments, reminders

### 7. Cron Job Report
- List all cron jobs: `cron list`
- Report: job count, next scheduled runs, any failures
- Check system health: `ps aux | grep nanobot`

## Output Format

Generate a well-formatted markdown briefing with:

```
# 📰 Morning Briefing - [DATE]

---

## 🌍 World News
[Headlines with summaries]

## 💻 Tech & AI News
[Major tech/AI stories]

## 🤖 Unrestricted Models
[Trending uncensored models]

## 🌤️ Weather - Quakers Hill
[Current conditions + forecast]

## 📧 Email Status
[Inbox summary]

## 📅 Calendar
[Today's events]

## ⚙️ System & Cron Jobs
[Active jobs, system status]

## 📋 Action Items
[Any tasks to do today]

---

*Generated: [timestamp]*
```

## Notes

- Make the briefing LENGTHY and COMPREHENSIVE
- Don't skip any section
- Include as much detail as possible in each section
- Save to `/home/nanobot/.nanobot/workspace/morning_briefing.md`
- The briefing should be something the user can read over coffee ☕