# Voice controls in LifePilot Circles

The AI Assistant now supports **browser microphone dictation** and **spoken plan previews**.

## Use
1. Open AI Assistant.
2. Select English or Hindi; click **Speak**. Your browser requests microphone access.
3. Say an action like "Assign Rahul the backend task by Friday".
4. Review/edit the transcript before pressing **Generate plan**.
5. Use the speaker icon in the plan preview to hear its summary.
6. Explicitly **Approve** or **Reject**. Voice input does not approve actions automatically.

## Privacy and browser support

Uses browser SpeechRecognition / webkitSpeechRecognition, which may route speech
audio to the browser provider depending on browser configuration. LifePilot does
not intentionally upload raw microphone recordings itself. Review your browser
speech privacy settings. Voice support varies by browser; Chrome/Edge over HTTPS
or localhost are recommended. The app falls back to text entry otherwise.

Plan previews use browser speechSynthesis text-to-speech. Support and voices vary.
Neither voice input nor speech output initiates automatic tool execution.

## Alexa+ is a separate integration

Browser speech does **not** register LifePilot with Alexa. The existing MCP
server and Vercel internal services are not automatically accessible to Alexa
devices. Real Alexa+ support requires an authorized skill/agent integration,
suitable public authenticated MCP endpoint when needed, account linking/OAuth
and separate Alexa developer testing. No claim of Alexa certification.
