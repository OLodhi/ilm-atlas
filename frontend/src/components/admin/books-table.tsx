"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminBooks } from "@/hooks/use-admin-books";

export function BooksTable() {
  const { books, loading, error } = useAdminBooks();

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

  if (books.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No books in the knowledge base yet.
      </p>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Title</TableHead>
          <TableHead>Author</TableHead>
          <TableHead>Language</TableHead>
          <TableHead>Madhab</TableHead>
          <TableHead>Category</TableHead>
          <TableHead>Added</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {books.map((book) => (
          <TableRow key={book.id}>
            <TableCell className="font-medium">{book.title}</TableCell>
            <TableCell>{book.author || "-"}</TableCell>
            <TableCell className="capitalize">{book.language}</TableCell>
            <TableCell className="capitalize">{book.madhab}</TableCell>
            <TableCell className="capitalize">{book.category}</TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {new Date(book.created_at).toLocaleDateString()}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
