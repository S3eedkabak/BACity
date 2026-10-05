import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { Linking, Text, View } from "react-native";
import { apiRequest } from "../src/api/client";
import {
  Page,
  Card,
  Disclosure,
  Field,
  Button,
  Chip,
  Notice,
  ui,
} from "../src/components/CommunityUI";
import { TemporalField } from '../src/components/TemporalField';

export default function Organizer() {
  const [eventDate, setEventDate] = useState('');
  const [eventTime, setEventTime] = useState('18:00');
  const { claim } = useLocalSearchParams<{ claim?: string }>();
  const [orgs, setOrgs] = useState<any[]>([]);
  const [organization, setOrganization] = useState<any>(null);
  const [selected, setSelected] = useState("");
  const [analytics, setAnalytics] = useState<any>(null);
  const [billing, setBilling] = useState<any>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [claimOrganization, setClaimOrganization] = useState<any>(null);
  const [evidence, setEvidence] = useState("");
  const [newName, setNewName] = useState("");
  const [newWebsite, setNewWebsite] = useState("");

  useEffect(() => {
    apiRequest<any[]>("/organizer/organizations", { auth: true })
      .then(setOrgs)
      .catch((e) => setNotice(e.message));
    apiRequest("/billing/status")
      .then(setBilling)
      .catch((e) => setNotice(e.message));
    if (claim) apiRequest<any[]>('/community/organizations').then(items => setClaimOrganization(items.find(item => item.id === claim) ?? null)).catch(e => setNotice(e.message));
  }, [claim]);

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
    <Page title="Organizer tools">
      <Notice text={notice} />
      <Button title="Browse organizers" onPress={() => router.push({ pathname: "/(tabs)/explore", params: { domain: "organizers" } })} />

      {claimOrganization && <Card><Text style={ui.heading}>Claim {claimOrganization.name}</Text><Text style={ui.text}>Provide a public HTTPS page that proves your relationship to this organization.</Text><Field label="Public ownership evidence URL" value={evidence} onChange={setEvidence} /><Button title="Request ownership review" busy={busy} onPress={async () => { setBusy(true); try { await apiRequest(`/community/organizations/${claimOrganization.id}/claim`, { method: 'POST', auth: true, body: { evidence_url: evidence, reason: 'Please verify my ownership using the supplied public evidence' } }); setNotice('Ownership claim submitted for moderation.'); } catch (e: any) { setNotice(e.message); } finally { setBusy(false); } }} /></Card>}

<Disclosure title="Register an organization"><Field label="Organization name" value={newName} onChange={setNewName} /><Field label="Official website (HTTPS)" value={newWebsite} onChange={setNewWebsite} /><Button title="Create organization profile" busy={busy} onPress={async () => { setBusy(true); try { const created = await apiRequest<any>('/community/organizations', { method: 'POST', auth: true, body: { name: newName, website: newWebsite, description: null, venue_id: null } }); setNotice(`Created ${created.name}. Claim it from Explore to verify ownership.`); setNewName(''); setNewWebsite(''); } catch (e: any) { setNotice(e.message); } finally { setBusy(false); } }} /></Disclosure>

      {!orgs.length ? (
        <Card>
          <Text style={ui.heading}>No organization yet</Text>
          <Text style={ui.text}>
            Find an organization in Explore, submit ownership evidence, and wait for verification to manage it here.
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

      {Boolean(selected) && (
        <>
          {organization && <Disclosure title="Organization profile"><Field label="Name" value={organization.name} onChange={name => setOrganization({ ...organization, name })} /><Field label="Description" value={organization.description ?? ''} onChange={description => setOrganization({ ...organization, description })} multiline /><Button title="Save organization profile" busy={busy} onPress={async () => { setBusy(true); try { await apiRequest(`/community/organizations/${selected}`, { method: 'PATCH', auth: true, body: { name: organization.name, description: organization.description, website: organization.website, venue_id: organization.venue_id } }); setOrgs(current => current.map(org => org.id === selected ? { ...org, name: organization.name } : org)); setNotice('Organization updated.'); } catch (e: any) { setNotice(e.message); } finally { setBusy(false); } }} /></Disclosure>}
          {analytics && (
            <Card>
              <Text style={ui.heading}>Audience</Text>
              <Text style={ui.text}>
                {analytics.events} events · {analytics.followers} followers · {analytics.saves} saves
              </Text>
            </Card>
          )}

          <Disclosure title="Publish an event or recurring series" initiallyOpen>
            {field("title", "Title")}
            {field("description", "Description", true)}
            {field("address", "Address in Bratislava")}
            {field("source", "Official event URL (optional, HTTPS)")}
            <TemporalField label="Event date" value={eventDate} onChange={setEventDate} />
            <TemporalField label="Start time" mode="time" value={eventTime} onChange={setEventTime} />
            <Button variant="secondary" title="Add this occurrence" onPress={() => {
              const date = new Date(`${eventDate}T${eventTime}`);
              if (Number.isNaN(date.getTime())) { setNotice('Choose a valid event date and time.'); return; }
              setFields(current => ({ ...current, dates: [...(current.dates || '').split('\n').filter(Boolean), date.toISOString()].join('\n') }));
            }} />
            {(fields.dates || '').split('\n').filter(Boolean).map((value, index) => <Text key={index} style={ui.text}>{new Date(value).toLocaleString()}</Text>)}
            <Disclosure title="Edit all dates" icon="calendar-outline">{field('dates', 'Start dates including timezone, one per line', true)}</Disclosure>
            <Button title="Publish dates" busy={busy} onPress={publish} />
          </Disclosure>

          <Disclosure title="Subscription">
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
          </Disclosure>
        </>
      )}
    </Page>
  );
}
