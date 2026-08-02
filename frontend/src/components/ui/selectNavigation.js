function isEnabled(option) {
  return !option?.disabled
}

export function getEnabledOptionIndex(options, value) {
  const selectedIndex = options.findIndex((option) => String(option.value) === String(value) && isEnabled(option))
  if (selectedIndex >= 0) return selectedIndex
  return options.findIndex(isEnabled)
}

export function getNextEnabledOptionIndex(options, currentIndex, direction) {
  const enabledIndices = options.map((option, index) => (isEnabled(option) ? index : -1)).filter((index) => index >= 0)
  if (!enabledIndices.length) return -1
  if (direction === 'home') return enabledIndices[0]
  if (direction === 'end') return enabledIndices.at(-1)

  const currentPosition = enabledIndices.indexOf(currentIndex)
  if (currentPosition < 0) return direction < 0 ? enabledIndices.at(-1) : enabledIndices[0]
  return enabledIndices[(currentPosition + direction + enabledIndices.length) % enabledIndices.length]
}
