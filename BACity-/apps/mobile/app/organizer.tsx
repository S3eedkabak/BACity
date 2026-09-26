import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Linking, Text, View } from "react-native";
import { apiRequest } from "../src/api/client";
import {
  Page,
  Card,
  Field,
  Button,
  Chip,
  Notice,
  ui,
} from "../src/components/CommunityUI";

export default function Organizer() {
  const [orgs, setOrgs] = useState<any[]>([]);
  const [organization, setOrganization] = useState<any>(null);
  const [selected, setSelected] = useState("");
  const [analytics, setAnalytics] = useState<any>(null);
  const [billing, setBilling] = useState<any>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiRequest<any[]>("/organizer/organizations", { auth: true })
      .then(setOrgs)
      .catch((e) => setNotice(e.message));
    apiRequest("/billing/status")
      .then(setBilling)
      .catch((e) => setNotice(e.message));
  }, []);

  async function choose(id: string) {
    setSelected(id);
    setOrganization(null);
    setAnalytics(null);
    setNotice("");
    try {
      const organizations = await apiRequest<any[]>('/community/organizations');
      setOrganization(organizations.find(org => org.id === id) ?? null);
      setAnalytics(await apiRequest(`/organizer/${id}/analytics`, { auth: true }));
    } catch (e: any) {
      setNotice(e.message);
    }
  }

  function field(key: string, label: string, multiline = false) {
    return (
      <Field
        key={key}
        label={label}
        value={fields[key] ?? ""}
        onChange={(value) => setFields({ ...fields, [key]: value })}
        multiline={multiline}
      />
    );
  }

  async function publish() {
    setBusy(true);
    setNotice("");
    try {
      const dates = (fields.dates ?? "")
        .split("\n")
        .map((date) => date.trim())
        .filter(Boolean);
      await apiRequest(`/organizer/${selected}/events`, {
        method: "POST",
        auth: true,
        body: {
          dates,
          event: {
            title: fields.title,
            description: fields.description,
            address: fields.address,
            source_url: fields.source,
            start_time: dates[0],
            category: "Community",
          },
        },
      });
      await choose(selected);
      setNotice("Events published and followers notified.");
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function payment(path: string, body?: unknown) {
    setBusy(true);
    setNotice("");
    try {
      const result = await apiRequest<{ url: string }>(path, {
        method: "POST",
        auth: true,
        body,
      });
      await Linking.openURL(result.url);
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page title="Organizer dashboard">
      <Notice text={notice} />
      <Button title="Find or register an organization" onPress={() => router.push("/community?section=organizations")} />

      {!orgs.length ? (
        <Card>
          <Text style={ui.heading}>No organization yet</Text>
          <Text style={ui.text}>
            Claim an organization from Community and wait for ownership verification to manage it here.
          </Text>
        </Card>
      ) : (
        <>
          <Text style={ui.muted}>Choose an organization</Text>
          <View style={ui.row}>
            {orgs.map((org) => (
              <Chip
                key={org.id}
                title={`${org.name} · ${org.tier}`}
                active={selected === org.id}
                onPress={() => choose(org.id)}
              />
            ))}
          </View>
        </>
      )}

      {selected && (
        <>
          {organization && <Card><Text style={ui.heading}>Organization profile</Text><Field label="Name" value={organization.name} onChange={name => setOrganization({ ...organization, name })} /><Field label="Description" value={organization.description ?? ''} onChange={description => setOrganization({ ...organization, description })} multiline /><Button title="Save organization profile" busy={busy} onPress={async () => { setBusy(true); try { await apiRequest(`/community/organizations/${selected}`, { method: 'PATCH', auth: true, body: { name: organization.name, description: organization.description, website: organization.website, venue_id: organization.venue_id } }); setOrgs(current => current.map(org => org.id === selected ? { ...org, name: organization.name } : org)); setNotice('Organization updated.'); } catch (e: any) { setNotice(e.message); } finally { setBusy(false); } }} /></Card>}
          {analytics && (
            <Card>
              <Text style={ui.heading}>Audience</Text>
              <Text style={ui.text}>
                {analytics.events} events · {analytics.followers} followers · {analytics.saves} saves
              </Text>
            </Card>
          )}

          <Card>
            <Text style={ui.heading}>Publish an event or recurring series</Text>
            {field("title", "Title")}
            {field("description", "Description", true)}
            {field("address", "Address in Bratislava")}
            {field("source", "Official event URL (HTTPS)")}
            {field(
              "dates",
              "One start date per line, with timezone (e.g. 2026-12-10T19:00+01:00)",
              true
            )}
            <Button title="Publish dates" busy={busy} onPress={publish} />
          </Card>

          <Card>
            <Text style={ui.heading}>Subscription</Text>
            {billing?.configured ? (
              <>
                {billing.plans.map((tier: string) => (
                  <Button
                    key={tier}
                    title={"Review " + tier + " pricing in checkout"}
                    busy={busy}
                    onPress={() =>
                      payment("/billing/checkout", {
                        organization_id: selected,
                        tier,
                      })
                    }
                  />
                ))}
                <Button
                  title="Manage or cancel subscription"
                  busy={busy}
                  onPress={() => payment(`/billing/portal/${selected}`)}
                />
              </>
            ) : (
              <Text style={ui.text}>
                Paid plans are not available yet. Payment services have not been configured.
              </Text>
            )}
          </Card>
        </>
      )}
    </Page>
  );
}
