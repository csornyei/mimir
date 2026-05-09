import { useEffect } from 'react'
import { RouterProvider } from 'react-router'
import { router } from '@/router'
import { Toaster } from '@/components/ui/sonner'
import { useMimirStore } from '@/store'

export default function App() {
  const initWs = useMimirStore((s) => s.initWs)
  const loadConversations = useMimirStore((s) => s.loadConversations)

  useEffect(() => {
    initWs()
    loadConversations().catch(() => {})
  }, [initWs, loadConversations])

  return (
    <>
      <RouterProvider router={router} />
      <Toaster position="bottom-right" />
    </>
  )
}
