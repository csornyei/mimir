import { createBrowserRouter } from 'react-router'
import { AppShell } from '@/components/layout/AppShell'
import { ChatScreen } from '@/screens/ChatScreen'
import { MemoryScreen } from '@/screens/MemoryScreen'
import { BriefScreen } from '@/screens/BriefScreen'
import { DigestScreen } from '@/screens/DigestScreen'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <ChatScreen /> },
      { path: 'c/:conversationId', element: <ChatScreen /> },
      { path: 'memory', element: <MemoryScreen /> },
      { path: 'digest', element: <DigestScreen /> },
      { path: 'brief', element: <BriefScreen /> },
    ],
  },
])
