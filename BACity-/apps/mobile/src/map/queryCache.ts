import type { QueryClient } from '@tanstack/react-query';

export function trimMapQueries(client: QueryClient) {
  const inactive = client.getQueryCache().findAll({queryKey:['map-identities']})
    .filter(query=>!query.isActive()).sort((a,b)=>b.state.dataUpdatedAt-a.state.dataUpdatedAt);
  for (const query of inactive.slice(7)) client.removeQueries({queryKey:query.queryKey,exact:true});
}
