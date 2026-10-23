import { useEffect, useRef } from 'react'

const FOCUSABLE = 'a[href]:not([tabindex="-1"]), button:not([disabled]):not([tabindex="-1"]), input:not([disabled]):not([tabindex="-1"]), select:not([disabled]):not([tabindex="-1"]), textarea:not([disabled]):not([tabindex="-1"]), [tabindex]:not([tabindex="-1"])'

export function useDialogFocus(dialogRef, onClose, enabled = true, initialSelector = FOCUSABLE) {
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    const dialog = dialogRef.current
    if (!enabled || !dialog) return undefined

    const previousFocus = document.activeElement
    const focusables = () => [...dialog.querySelectorAll(FOCUSABLE)].filter((node) => node.getClientRects().length)
    const initial = dialog.querySelector(initialSelector)
    ;(initial || focusables()[0] || dialog).focus()

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab') return

      const nodes = focusables()
      if (!nodes.length) {
        event.preventDefault()
        dialog.focus()
        return
      }
      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog)) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus()
    }
  }, [dialogRef, enabled, initialSelector])
}
