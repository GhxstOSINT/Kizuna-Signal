import type { FormEvent } from 'react'
import { useI18n } from './index'

type Field = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement

/** The browser words its own validation bubbles in the browser's language, so Japanese ones are written here. */
function japaneseMessage(field: Field): string {
  const state = field.validity
  const input = field as HTMLInputElement
  if (state.valueMissing) return 'このフィールドを入力してください。'
  if (state.tooShort) return `${input.minLength}文字以上で入力してください（現在は${field.value.length}文字です）。`
  if (state.tooLong) return `${input.maxLength}文字以内で入力してください。`
  if (state.typeMismatch) return input.type === 'url' ? 'URLを入力してください（例: https://example.com）。' : '有効な値を入力してください。'
  if (state.rangeUnderflow) return `${input.min}以上の値を入力してください。`
  if (state.rangeOverflow) return `${input.max}以下の値を入力してください。`
  if (state.badInput || state.patternMismatch) return '有効な値を入力してください。'
  return ''
}

/** Spread onto a <form>: Japanese validation messages while the interface is Japanese. */
export function useFormValidity() {
  const { lang } = useI18n()
  return {
    onInvalidCapture: (event: FormEvent<HTMLFormElement>) => {
      const field = event.target as Field
      field.setCustomValidity('')
      if (lang === 'ja') field.setCustomValidity(japaneseMessage(field))
    },
    onInputCapture: (event: FormEvent<HTMLFormElement>) => (event.target as Field).setCustomValidity?.(''),
  }
}
