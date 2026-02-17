"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/shared/status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminSources } from "@/hooks/use-admin-sources";

export function SourcesTable() {
  const { sources, loading, error } = useAdminSources();

  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-sm text-destructive">{error}</div>
    );
  }

  if (sources.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No sources uploaded yet.
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Filename</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Error</TableHead>
          <TableHead>Created</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sources.map((source) => (
          <TableRow key={source.id}>
            <TableCell className="font-medium">
              {source.filename}
            </TableCell>
            <TableCell>{source.file_type}</TableCell>
            <TableCell>
              <StatusBadge status={source.status} />
            </TableCell>
            <TableCell className="max-w-[200px] truncate text-sm text-muted-foreground">
              {source.error_message ?? "-"}
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {new Date(source.created_at).toLocaleDateString()}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
