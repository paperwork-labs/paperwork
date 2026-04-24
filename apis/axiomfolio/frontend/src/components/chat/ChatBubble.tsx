import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import { MessageCircle, X } from "lucide-react"

import { useChatContext } from "./ChatProvider"
import { ChatPanel } from "./ChatPanel"
import { useChatKeyboard } from "./useChatKeyboard"
import { cn } from "@/lib/utils"

export function ChatBubble() {
  const { isOpen, toggleChat, isOnAgentPage, messages } = useChatContext()
  const prefersReducedMotion = useReducedMotion()

  useChatKeyboard()

  if (isOnAgentPage) return null

  const hasMessages = messages.length > 0

  return (
    <>
      <AnimatePresence>{isOpen && <ChatPanel />}</AnimatePresence>

      <motion.button
        type="button"
        className={cn(
          "fixed bottom-6 right-6 z-50 flex size-14 items-center justify-center rounded-full shadow-lg",
          "bg-primary text-primary-foreground",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        )}
        whileHover={prefersReducedMotion ? {} : { scale: 1.05 }}
        whileTap={prefersReducedMotion ? {} : { scale: 0.95 }}
        onClick={toggleChat}
        aria-label={isOpen ? "Close agent chat" : "Open agent chat (Cmd/Ctrl+K)"}
        aria-expanded={isOpen}
      >
        <AnimatePresence mode="wait" initial={false}>
          {isOpen ? (
            <motion.div
              key="close"
              initial={
                prefersReducedMotion
                  ? { rotate: 0, opacity: 0 }
                  : { rotate: -90, opacity: 0 }
              }
              animate={{ rotate: 0, opacity: 1 }}
              exit={
                prefersReducedMotion
                  ? { rotate: 0, opacity: 0 }
                  : { rotate: 90, opacity: 0 }
              }
              transition={{ duration: 0.15 }}
            >
              <X className="size-6" />
            </motion.div>
          ) : (
            <motion.div
              key="open"
              initial={
                prefersReducedMotion
                  ? { rotate: 0, opacity: 0 }
                  : { rotate: 90, opacity: 0 }
              }
              animate={{ rotate: 0, opacity: 1 }}
              exit={
                prefersReducedMotion
                  ? { rotate: 0, opacity: 0 }
                  : { rotate: -90, opacity: 0 }
              }
              transition={{ duration: 0.15 }}
            >
              <MessageCircle className="size-6" />
            </motion.div>
          )}
        </AnimatePresence>

        {!isOpen && hasMessages && (
          <span className="absolute -top-0.5 -right-0.5 flex size-3">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary-foreground/60" />
            <span className="relative inline-flex size-3 rounded-full bg-primary-foreground" />
          </span>
        )}
      </motion.button>
    </>
  )
}
