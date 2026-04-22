function qs(sel, root) {
  return (root || document).querySelector(sel)
}

function qsa(sel, root) {
  return Array.from((root || document).querySelectorAll(sel))
}

function initSidebar() {
  var shell = qs('#appShell')
  var toggle = qs('#sidebarToggle')
  if (!shell || !toggle) return

  function setCollapsed(collapsed) {
    if (collapsed) {
      shell.classList.add('sidebar-collapsed')
      toggle.setAttribute('aria-expanded', 'false')
      localStorage.setItem('sidebarCollapsed', '1')
    } else {
      shell.classList.remove('sidebar-collapsed')
      toggle.setAttribute('aria-expanded', 'true')
      localStorage.setItem('sidebarCollapsed', '0')
    }
  }

  var saved = localStorage.getItem('sidebarCollapsed')
  if (saved === '1') setCollapsed(true)

  toggle.addEventListener('click', function () {
    setCollapsed(!shell.classList.contains('sidebar-collapsed'))
  })
}

function initStudentPicker() {
  qsa('[data-student-picker]').forEach(function (root) {
    var input = qs('#studentSearch', root)
    var list = qs('#pickerList', root)
    var hint = qs('#pickerHint', root)
    if (!input || !list || !hint) return

    var minLen = parseInt(input.getAttribute('data-min') || '3', 10)
    var items = qsa('.picker-item', list)

    function applyFilter() {
      var q = (input.value || '').trim().toLowerCase()
      if (q.length < minLen) {
        hint.textContent = 'Type ' + minLen + '+ characters to search'
        items.forEach(function (el) {
          el.classList.add('hidden')
        })
        return
      }

      hint.textContent = 'Select students to enroll'
      var shown = 0
      items.forEach(function (el) {
        var text = (el.getAttribute('data-text') || '')
        var match = text.indexOf(q) !== -1
        if (match && shown < 30) {
          el.classList.remove('hidden')
          shown += 1
        } else {
          el.classList.add('hidden')
        }
      })
    }

    input.addEventListener('input', applyFilter)
    applyFilter()
  })
}

document.addEventListener('DOMContentLoaded', function () {
  initSidebar()
  initStudentPicker()
})

