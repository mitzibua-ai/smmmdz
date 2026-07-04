/** Team dashboards — owner / admin / staff (manual refresh only). */
const ROLE_VIEWS = new Set(["owner", "admin", "staff"]);

function panelRole(acc = window.account || getAccount()) {
  return acc?.panelRole || (acc?.isOwner ? "owner" : acc?.isAdmin ? "admin" : acc?.isStaff ? "staff" : "member");
}

function isOwnerAccount(acc = getAccount()) {
  if (typeof isConfigOwner === "function" && isConfigOwner(acc)) return true;
  return panelRole(acc) === "owner";
}

function isAdminAccount(acc = getAccount()) {
  return ["owner", "admin"].includes(panelRole(acc));
}

function isStaffAccount(acc = getAccount()) {
  return ["owner", "admin", "staff"].includes(panelRole(acc));
}

function roleLabel(role) {
  return { owner: "Owner", admin: "Admin", staff: "Staff", member: "Member" }[role] || "Member";
}

function roleBadgeClass(role) {
  return `role-badge role-badge--${role || "member"}`;
}

function avatarUrlForUser(user) {
  const id = user.discordId;
  const hash = user.avatarHash;
  if (id && hash) {
    return `https://cdn.discordapp.com/avatars/${id}/${hash}.png?size=64`;
  }
  if (id) {
    const idx = Number(BigInt(id) % 6n);
    return `https://cdn.discordapp.com/embed/avatars/${idx}.png`;
  }
  return "";
}

async function registerUserOnServer(acc) {
  if (!acc?.discordId || !window.location.protocol.startsWith("http")) return null;
  try {
    if (typeof apiRequest === "function") {
      return await apiRequest("/api/users/register", {
        method: "POST",
        body: {
          discordId: acc.discordId,
          username: acc.username,
          avatarHash: acc.avatarHash || null,
        },
      });
    }
    const siteToken = typeof siteApiToken === "function" ? siteApiToken() : "";
    const res = await fetch(apiUrl("/api/users/register"), {
      method: "POST",
      mode: "cors",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(siteToken ? { "X-Site-Token": siteToken } : {}),
      },
      body: JSON.stringify({
        discordId: acc.discordId,
        username: acc.username,
        avatarHash: acc.avatarHash || null,
        accessToken: acc.discordAccessToken || null,
      }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function fetchTeamDashboard(kind) {
  const acc = getAccount();
  if (!acc?.discordId) throw new Error("Sign in with Discord first.");

  const path = `/api/${kind}/overview?discordId=${encodeURIComponent(acc.discordId)}`;

  function mapDashboardError(err) {
    if (err?.status === 403) {
      throw new Error("Access denied — you need Owner permissions on the API.");
    }
    if (typeof apiFetchErrorMessage === "function") {
      throw new Error(apiFetchErrorMessage(err));
    }
    throw new Error(err?.message || "Could not load dashboard.");
  }

  if (typeof apiGet === "function") {
    try {
      return await apiGet(path);
    } catch (err) {
      mapDashboardError(err);
    }
  }

  if (typeof apiRequest === "function") {
    try {
      return await apiRequest(path, { method: "GET" });
    } catch (err) {
      mapDashboardError(err);
    }
  }

  const res = await fetch(apiUrlWithToken(path), {
    method: "GET",
    mode: "cors",
    cache: "no-store",
  });
  if (res.status === 403) throw new Error("Access denied.");
  if (!res.ok) throw new Error("Could not load dashboard.");
  return res.json();
}

async function revokeLicense(targetId) {
  if (typeof apiRequest === "function") {
    return apiRequest("/api/owner/users/revoke-license", {
      method: "POST",
      body: { targetId },
    });
  }
  throw new Error("API not available.");
}

async function promoteUser(kind, targetId, role) {
  if (typeof getValidAccessToken === "function") {
    await getValidAccessToken(getAccount());
  }

  if (typeof apiRequest === "function") {
    return apiRequest(kind === "owner" ? "/api/owner/users/role" : "/api/admin/users/role", {
      method: "POST",
      body: { targetId, role },
    });
  }

  const acc = getAccount();
  const endpoint = kind === "owner" ? "/api/owner/users/role" : "/api/admin/users/role";
  const siteToken = typeof siteApiToken === "function" ? siteApiToken() : "";
  const res = await fetch(apiUrlWithToken(endpoint), {
    method: "POST",
    mode: "cors",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(siteToken ? { "X-Site-Token": siteToken } : {}),
    },
    body: JSON.stringify({
      discordId: acc.discordId,
      accessToken: acc.discordAccessToken || null,
      targetId,
      role,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Promotion failed.");
  return data;
}

function teamDashboardMeta(kind) {
  const map = {
    owner: {
      title: "Owner Command",
      subtitle: "Full platform control — manage users, roles, and activity.",
      badge: "Owner",
      className: "owner",
      canPromoteAdmin: true,
      canPromoteStaff: true,
    },
    admin: {
      title: "Admin Control",
      subtitle: "Manage staff and monitor platform activity.",
      badge: "Admin",
      className: "admin",
      canPromoteAdmin: false,
      canPromoteStaff: true,
    },
    staff: {
      title: "Staff Hub",
      subtitle: "Support overview — recent checks and live activity.",
      badge: "Staff",
      className: "staff",
      canPromoteAdmin: false,
      canPromoteStaff: false,
    },
  };
  return map[kind];
}

function renderTeamShell(kind) {
  const meta = teamDashboardMeta(kind);
  const addUserForm =
    kind === "owner"
      ? `
    <section class="panel panel--wide team-panel team-panel--add-user">
      <div class="panel__head">
        <div>
          <div class="panel__title">Add or promote a user</div>
          <div class="panel__sub">Enter a Discord ID and assign a role.</div>
        </div>
      </div>
      <div class="panel__body panel__body--flush team-add-user-form">
        <div class="team-add-user-row">
          <input class="form__input" id="team-add-user-id" type="text" placeholder="Discord user ID" />
          <select class="form__input" id="team-add-user-role">
            <option value="owner">Owner</option>
            <option value="admin">Admin</option>
            <option value="staff">Staff</option>
          </select>
          <button type="button" class="btn btn--primary btn--small" id="team-add-user-btn">Assign Role</button>
        </div>
        <p class="team-footnote">This assigns a panel role by Discord ID and creates a site user placeholder if needed.</p>
      </div>
    </section>
  `
      : "";

  return `
    <header class="page-header page-header--team page-header--${meta.className}">
      <div>
        <h1>${meta.title}</h1>
        <p>${meta.subtitle}</p>
      </div>
      <div class="team-header__actions">
        <span class="badge badge--${meta.className}">${meta.badge} only</span>
        <button type="button" class="btn btn--ghost btn--small" id="team-refresh-btn">Refresh</button>
      </div>
    </header>
    ${addUserForm}
    <div id="team-dashboard-body" data-team-kind="${kind}">
      <div class="empty-state">Loading…</div>
    </div>
  `;
}

function closeTeamActionMenus() {
  document.querySelectorAll("#team-dashboard-body .action-menu__dropdown").forEach((menu) => {
    menu.classList.add("hidden");
  });
  document.querySelectorAll("#team-dashboard-body .action-menu__trigger").forEach((trigger) => {
    trigger.setAttribute("aria-expanded", "false");
  });
}

function renderUserActions(user, kind) {
  const meta = teamDashboardMeta(kind);
  const role = user.panelRole || "member";
  const isCustomer = (user.licensedStatus || "").toLowerCase() === "customer" || user.licenseActive === true;

  if (role === "owner") return `<span class="team-muted">Protected</span>`;
  if (user.discordId === getAccount()?.discordId) return `<span class="team-muted">You</span>`;

  const items = [];
  if (meta.canPromoteStaff && role !== "staff") {
    items.push(
      `<button type="button" class="action-menu__item team-promote" data-target="${escapeHtml(user.discordId)}" data-role="staff" role="menuitem">Promote to Staff</button>`
    );
  }
  if (meta.canPromoteAdmin && role !== "admin") {
    items.push(
      `<button type="button" class="action-menu__item team-promote" data-target="${escapeHtml(user.discordId)}" data-role="admin" role="menuitem">Promote to Admin</button>`
    );
  }
  if (role !== "member" && (meta.canPromoteAdmin || (meta.canPromoteStaff && role === "staff"))) {
    items.push(
      `<button type="button" class="action-menu__item action-menu__item--danger team-promote" data-target="${escapeHtml(user.discordId)}" data-role="member" role="menuitem">Demote to Member</button>`
    );
  }
  if (kind === "owner" && isCustomer) {
    items.push(
      `<button type="button" class="action-menu__item action-menu__item--danger team-revoke-license" data-target="${escapeHtml(user.discordId)}" role="menuitem">Revoke License</button>`
    );
  }
  if (items.length) {
    items.push(`<div class="action-menu__sep"></div>`);
  }
  items.push(
    `<button type="button" class="action-menu__item team-copy-id" data-id="${escapeHtml(user.discordId)}" role="menuitem">Copy Discord ID</button>`
  );

  return `
    <div class="action-menu">
      <button type="button" class="action-menu__trigger" aria-label="User actions" aria-haspopup="true" aria-expanded="false">
        <span class="action-menu__dots" aria-hidden="true"><span></span><span></span><span></span></span>
      </button>
      <div class="action-menu__dropdown hidden" role="menu">
        ${items.join("")}
      </div>
    </div>
  `;
}

function userDisplayToken(user) {
  return user?.userToken || user?.discordId || "—";
}

function renderTeamUsersTable(users, kind) {
  if (!users?.length) {
    return `<div class="empty-state team-empty">No users yet. They appear here after Discord login.</div>`;
  }

  const isOwnerView = kind === "owner";
  const rows = users
    .map((user) => {
      const avatar = avatarUrlForUser(user);
      const token = userDisplayToken(user);
      return `
        <tr class="team-user-row" data-discord-id="${escapeHtml(user.discordId)}">
          <td>
            <div class="team-user">
              <img class="team-user__avatar" src="${avatar}" alt="" width="40" height="40" loading="lazy" />
              <div class="team-user__name">${escapeHtml(user.username || "Unknown")}</div>
            </div>
          </td>
          <td><code class="team-user__id">${escapeHtml(user.discordId || "—")}</code></td>
          <td>
            <div class="team-token-cell">
              <code class="team-user__token" title="Site token">${escapeHtml(token)}</code>
              <button type="button" class="btn btn--ghost btn--tiny team-copy-token" data-token="${escapeHtml(token)}" title="Copy token">Copy</button>
            </div>
          </td>
          <td><span class="${roleBadgeClass(user.panelRole)}">${roleLabel(user.panelRole)}</span></td>
          <td><span class="license-pill license-pill--${(user.licensedStatus || "standard").toLowerCase()}">${escapeHtml(user.licensedStatus || "Standard")}</span></td>
          ${isOwnerView ? "" : `<td>${user.pins || 0}</td><td>${user.scans || 0}</td><td>${formatDate(user.lastSeen || user.firstSeen)}</td>`}
          <td class="team-actions-cell">${renderUserActions(user, kind)}</td>
        </tr>`;
    })
    .join("");

  const extraCols = isOwnerView
    ? ""
    : `<th>Pins</th><th>Scans</th><th>Last seen</th>`;

  return `
    <div class="team-toolbar">
      <input type="search" class="form__input team-search" id="team-user-search" placeholder="Search username, Discord ID, or token…" />
      <span class="team-user-count">${users.length} user${users.length === 1 ? "" : "s"}</span>
    </div>
    <div class="owner-table-wrap">
      <table class="owner-table team-table team-table--users">
        <thead>
          <tr>
            <th>Username</th>
            <th>Discord ID</th>
            <th>Token</th>
            <th>Role</th>
            <th>License</th>
            ${extraCols}
            <th>Actions</th>
          </tr>
        </thead>
        <tbody id="team-users-tbody">${rows}</tbody>
      </table>
    </div>
  `;
}

function renderActivityList(items, type) {
  if (!items?.length) return `<div class="empty-state">No ${type} yet.</div>`;
  return items
    .map((item) => {
      if (type === "scans") {
        return `
          <div class="scan-row">
            <div>
              <div class="scan-row__name">${escapeHtml(item.playerName || "—")}</div>
              <div class="scan-row__date">${formatDate(item.date)} · ${escapeHtml(item.username || item.discordId || "")}</div>
            </div>
            <span class="tag ${verdictClass(item.verdict)}">${verdictLabel(item.verdict)}</span>
          </div>`;
      }
      return `
        <div class="scan-row">
          <div>
            <div class="scan-row__name">PIN ${escapeHtml(item.pin)} · ${escapeHtml(item.playerName || "—")}</div>
            <div class="scan-row__date">${formatDate(item.date)} · <code>${escapeHtml(item.discordId || "")}</code></div>
          </div>
          <span class="tag">${escapeHtml(item.result || item.status || "—")}</span>
        </div>`;
    })
    .join("");
}

function renderTeamData(data, kind) {
  const totals = data.totals || {};
  const verdicts = data.verdicts || {};
  const meta = teamDashboardMeta(kind);

  const userSection =
    kind === "staff"
      ? ""
      : `
    <section class="panels">
      <div class="panel panel--wide team-panel">
        <div class="panel__head">
          <div>
            <div class="panel__title">Registered users</div>
            <div class="panel__sub">Everyone who logged into dotx with Discord</div>
          </div>
        </div>
        <div class="panel__body panel__body--flush">${renderTeamUsersTable(data.siteUsers || [], kind)}</div>
      </div>
    </section>`;

  return `
    ${userSection}
    <section class="metrics metrics--team">
      <div class="metric metric--team"><div class="metric__label">Site users</div><div class="metric__value">${totals.siteUsers || 0}</div></div>
      <div class="metric metric--team"><div class="metric__label">Staff</div><div class="metric__value">${totals.staff || 0}</div></div>
      <div class="metric metric--team"><div class="metric__label">Admins</div><div class="metric__value">${totals.admins || 0}</div></div>
      <div class="metric metric--team"><div class="metric__label">Total scans</div><div class="metric__value">${totals.scans || 0}</div></div>
      <div class="metric metric--team"><div class="metric__label">Flagged</div><div class="metric__value">${(verdicts.failed || 0) + (verdicts.suspicious || 0)}</div></div>
    </section>
    ${kind === "owner" ? "" : `<section class="panels panels--bottom">
      <div class="panel">
        <div class="panel__head"><div><div class="panel__title">Recent scans</div><div class="panel__sub">Platform-wide</div></div></div>
        <div class="scan-table">${renderActivityList(data.recentScans, "scans")}</div>
      </div>
      <div class="panel">
        <div class="panel__head"><div><div class="panel__title">Recent pins</div><div class="panel__sub">Platform-wide</div></div></div>
        <div class="scan-table">${renderActivityList(data.recentPins, "pins")}</div>
      </div>
    </section>`}
    <p class="team-footnote">${meta.badge} dashboard does not auto-refresh. Click <strong>Refresh</strong> to update.</p>
  `;
}

async function loadTeamDashboard(kind, { silent = false } = {}) {
  const body = document.getElementById("team-dashboard-body");
  if (!body) return;
  if (!silent) body.innerHTML = `<div class="empty-state">Loading…</div>`;
  try {
    await registerUserOnServer(getAccount());
    let data;
    try {
      data = await fetchTeamDashboard(kind);
    } catch (firstErr) {
      await new Promise((r) => setTimeout(r, 600));
      data = await fetchTeamDashboard(kind);
    }
    body.innerHTML = renderTeamData(data, kind);
    bindTeamDashboardEvents(kind);
  } catch (err) {
    const message =
      typeof apiFetchErrorMessage === "function"
        ? apiFetchErrorMessage(err)
        : err.message || "Dashboard unavailable.";
    body.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
  }
}

function bindTeamDashboardEvents(kind) {
  document.getElementById("team-refresh-btn")?.addEventListener("click", () => {
    loadTeamDashboard(kind);
  });

  document.getElementById("team-add-user-btn")?.addEventListener("click", async () => {
    const targetId = document.getElementById("team-add-user-id")?.value.trim();
    const role = document.getElementById("team-add-user-role")?.value;
    if (!targetId) {
      alert("Enter a Discord ID.");
      return;
    }
    const btn = document.getElementById("team-add-user-btn");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Assigning…";
    }
    try {
      await promoteUser("owner", targetId, role);
      document.getElementById("team-add-user-id").value = "";
      await loadTeamDashboard(kind, { silent: true });
    } catch (err) {
      alert(err.message || "Could not assign role.");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Assign Role";
      }
    }
  });

  document.getElementById("team-user-search")?.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    document.querySelectorAll(".team-user-row").forEach((row) => {
      row.style.display = row.textContent.toLowerCase().includes(q) ? "" : "none";
    });
  });

  document.querySelectorAll(".team-promote").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      closeTeamActionMenus();
      const targetId = btn.dataset.target;
      const role = btn.dataset.role;
      const promoteKind = kind === "admin" ? "admin" : "owner";
      btn.disabled = true;
      const prev = btn.textContent;
      btn.textContent = "…";
      try {
        await promoteUser(promoteKind, targetId, role);
        await loadTeamDashboard(kind, { silent: true });
        const acc = getAccount();
        if (targetId === acc.discordId) {
          const refreshed = await applyLicensedStatus(acc);
          if (typeof handleLicenseUpdate === "function") handleLicenseUpdate(refreshed);
        }
      } catch (err) {
        alert(err.message || "Could not update role.");
        btn.disabled = false;
        btn.textContent = prev;
      }
    });
  });

  document.querySelectorAll(".team-revoke-license").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      closeTeamActionMenus();
      const targetId = btn.dataset.target;
      if (!targetId || !confirm("Revoke this customer's license? They will lose Pins and Reports access.")) return;
      btn.disabled = true;
      const prev = btn.textContent;
      btn.textContent = "…";
      try {
        await revokeLicense(targetId);
        await loadTeamDashboard(kind, { silent: true });
      } catch (err) {
        alert(err.message || "Could not revoke license.");
        btn.disabled = false;
        btn.textContent = prev;
      }
    });
  });

  document.querySelectorAll("#team-dashboard-body .action-menu__trigger").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const dropdown = btn.closest(".action-menu")?.querySelector(".action-menu__dropdown");
      const wasOpen = dropdown && !dropdown.classList.contains("hidden");
      closeTeamActionMenus();
      if (!wasOpen && dropdown) {
        dropdown.classList.remove("hidden");
        btn.setAttribute("aria-expanded", "true");
      }
    });
  });

  document.querySelectorAll(".team-copy-token").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const token = btn.dataset.token || "";
      try {
        await navigator.clipboard.writeText(token);
        btn.textContent = "Copied";
        setTimeout(() => {
          btn.textContent = "Copy";
        }, 1200);
      } catch {
        alert(token);
      }
    });
  });

  document.querySelectorAll(".team-copy-id").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const id = btn.dataset.id || "";
      try {
        await navigator.clipboard.writeText(id);
        btn.textContent = "Copied!";
        setTimeout(() => {
          btn.textContent = "Copy Discord ID";
        }, 1200);
      } catch {
        alert(id);
      }
      closeTeamActionMenus();
    });
  });

  if (!bindTeamDashboardEvents._outsideBound) {
    bindTeamDashboardEvents._outsideBound = true;
    document.addEventListener("click", closeTeamActionMenus);
  }
}

function updateRoleNav(acc = getAccount()) {
  const role = panelRole(acc);
  const ownerNav = document.getElementById("owner-nav");
  const adminNav = document.getElementById("admin-nav");
  const staffNav = document.getElementById("staff-nav");
  if (ownerNav) ownerNav.classList.toggle("hidden", role !== "owner");
  if (adminNav) adminNav.classList.toggle("hidden", !["owner", "admin"].includes(role));
  if (staffNav) staffNav.classList.toggle("hidden", !["owner", "admin", "staff"].includes(role));
}

function canAccessView(view, acc = getAccount()) {
  if (view === "owner") return isOwnerAccount(acc);
  if (view === "admin") return isAdminAccount(acc);
  if (view === "staff") return isStaffAccount(acc);
  if (view === "checks" || view === "reports") return true;
  return true;
}

function updateLicenseNav(acc = getAccount()) {
  const unlocked = isCustomerAccount(acc);
  document.querySelectorAll('.nav__item[data-view="checks"], .nav__item[data-view="reports"]').forEach((btn) => {
    btn.classList.toggle("nav__item--locked", !unlocked);
    const label = btn.querySelector(".nav__label");
    if (label && !label.dataset.baseLabel) {
      label.dataset.baseLabel = label.textContent.replace(/^🔒\s*/, "");
    }
    if (label) {
      label.textContent = unlocked ? label.dataset.baseLabel : `🔒 ${label.dataset.baseLabel}`;
    }
  });
}

function renderTeamView(kind) {
  return renderTeamShell(kind);
}

function initTeamView(kind) {
  loadTeamDashboard(kind);
}
