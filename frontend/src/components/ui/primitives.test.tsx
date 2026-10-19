import { fireEvent, render, screen } from '@testing-library/react';
import { Button } from './Button';
import { ButtonLink } from './ButtonLink';
import { AccordionItem } from './AccordionItem';
import { Container } from './Container';
import { Card } from './Card';
import { Badge } from './Badge';
import { SectionHeading } from './SectionHeading';

it('uses a native action button without submitting a surrounding form by default', () => {
  const action = jest.fn();
  const submit = jest.fn((event) => event.preventDefault());
  render(
    <form onSubmit={submit}>
      <Button onClick={action}>Continue</Button>
      <Button type="submit" variant="secondary">
        Submit
      </Button>
      <Button disabled variant="ghost" onClick={action}>
        Unavailable
      </Button>
    </form>,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
  expect(action).toHaveBeenCalledTimes(1);
  expect(submit).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
  expect(submit).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Unavailable' }));
  expect(action).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button', { name: 'Unavailable' })).toBeDisabled();
});

it('uses links for navigation and protects external new tabs', () => {
  render(
    <>
      <ButtonLink href="/">Home</ButtonLink>
      <ButtonLink href="https://example.org/" target="_blank">
        Reference
      </ButtonLink>
    </>,
  );
  expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute('href', '/');
  expect(screen.getByRole('link', { name: 'Reference' })).toHaveAttribute(
    'rel',
    expect.stringContaining('noopener noreferrer'),
  );
});

it('rejects executable external destinations', () => {
  expect(() => render(<ButtonLink href="javascript:alert(1)">Unsafe</ButtonLink>)).toThrow(
    'ButtonLink requires',
  );
});

it('renders caller content with explicit heading hierarchy and noninteractive surfaces', () => {
  render(
    <Container width="narrow">
      <SectionHeading level="h3" id="details" eyebrow="About" description="Supporting copy">
        Details
      </SectionHeading>
      <Card variant="dark">
        <Badge variant="success">Example label</Badge>
      </Card>
    </Container>,
  );
  expect(screen.getByRole('heading', { level: 3, name: 'Details' })).toHaveAttribute(
    'id',
    'details',
  );
  expect(screen.getByText('Supporting copy')).toBeVisible();
  expect(screen.getByText('Example label')).toBeVisible();
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});

it('uses a native disclosure with a text-bearing summary and initially hidden answer', () => {
  render(
    <AccordionItem title="A long question">
      <p>An answer</p>
      <ButtonLink href="/">Home</ButtonLink>
    </AccordionItem>,
  );
  const summary = screen.getByText('A long question');
  const details = summary.closest('details');
  expect(summary.tagName).toBe('SUMMARY');
  expect(details).not.toHaveAttribute('open');
  expect(screen.getByText('An answer')).not.toBeVisible();
  fireEvent.click(summary);
  expect(details).toHaveAttribute('open');
  expect(screen.getByText('An answer')).toBeVisible();
  fireEvent.click(summary);
  expect(details).not.toHaveAttribute('open');
});
